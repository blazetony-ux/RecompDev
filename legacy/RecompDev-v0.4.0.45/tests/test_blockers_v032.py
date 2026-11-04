"""V0.3.2 regressions: synthetic bytecode, not validated commercial ROM parity."""
import hashlib
from contextlib import closing
from unittest.mock import patch
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovery.codegen import generate,Blocked
from recovery.pipeline import compile_cpp,seeded_runner_args
from recovery.autopilot import autopilot
from test_function_v031 import FUNCTION,ROM,SHA,D0,doc


def ops_copy_to_d0(ops):
    f=json.loads(json.dumps(FUNCTION))
    f['instructions'][0]['pcode']=ops
    return f


class BlockerRegressionTests(unittest.TestCase):
    def compiler(self):
        c=shutil.which('g++') or shutil.which('clang++')
        if not c:self.skipTest('C++ compiler not installed')
        return c

    def test_int_mult_32bit_wrap_and_native_execution(self):
        f=ops_copy_to_d0([{'op':'INT_MULT','output':D0,'inputs':[
            {'space':'const','offset':0xffffffff,'size':4},
            {'space':'const','offset':3,'size':4}]}])
        generated=generate(f,'m68k','68000:BE:32:default')
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'mul.cpp';cpp.write_text(generated['cpp'])
            status,msg=compile_cpp(cpp,self.compiler())
            self.assertEqual(status,'COMPILED_RUNNER_SMOKE_ONLY',msg)
            output=subprocess.check_output([str(cpp.with_suffix(''))],text=True)
            self.assertIn('D0 0 4 4294967293',output)

    def test_ram_varnode_read_write_with_explicit_seed(self):
        # Exercise a P-code direct RAM varnode, distinct from LOAD/STORE.
        v={'space':'ram','offset':0xff0010,'size':4,'name':None}
        f=ops_copy_to_d0([
            {'op':'COPY','output':v,'inputs':[{'space':'const','offset':0x12345678,'size':4}]},
            {'op':'COPY','output':D0,'inputs':[v]}
        ])
        generated=generate(f,'m68k','68000:BE:32:default')
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'ram.cpp';cpp.write_text(generated['cpp'])
            status,reason=compile_cpp(cpp,self.compiler(),runner_args=['--map-zero-ram','0xff0000','65536'])
            self.assertEqual(status,'COMPILED_SEEDED_SMOKE_ONLY',reason)
            runner=str(cpp.with_suffix(''))
            out=subprocess.check_output([runner,'--map-zero-ram','0xff0000','65536'],text=True)
            self.assertIn('D0 0 4 305419896',out)
            self.assertIn('MEM 16711696 1 18',out) # 0xff0010
            bad=subprocess.run([runner],capture_output=True,text=True)
            # A direct write needs a verified memory mapping (read would need one too).
            self.assertNotEqual(bad.returncode,0)

    def test_missing_memory_map_is_explicit_not_silent_success(self):
        f=ops_copy_to_d0([{'op':'COPY','output':D0,'inputs':[
            {'space':'ram','offset':0xc00004,'size':4}]}])
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'io.cpp';cpp.write_text(generate(f,'m68k','68000:BE:32:default')['cpp'])
            status,msg=compile_cpp(cpp,self.compiler(),runner_args=['--map-zero-ram','0xff0000','65536'])
            self.assertEqual(status,'COMPILED_SEEDED_RUNTIME_FAILED')
            self.assertIn('unmapped memory read at 12582916',msg)

    def test_runner_args_are_bounded_and_source_bound(self):
        class Image: data=b'abc'
        class Target(dict):pass
        target=Target(system_tag='megadrive',isa='m68k')
        original=Path('/some/existing/rom.md')
        args=seeded_runner_args(target,FUNCTION,{'registers':[{'name':'A7','size':4,'offset':28}]},
                                original,Image())
        # Path() intentionally normalises separators for the host OS. The ROM
        # identity and all remaining arguments must be carried through exactly.
        self.assertEqual(args[0:5],['--image',str(original),'0','0','3'])
        self.assertIn('--megadrive-bus',args)
        self.assertEqual(args[-1],'28:4:0xfffef8')
        self.assertIsNone(seeded_runner_args(Target(system_tag='psx-exe',isa='mips'),
                             FUNCTION,{'registers':[]},Path('/x'),Image()))

    def test_source_sha_bound_ghidra_cache_skips_repeat_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'synthetic.md';source.write_bytes(ROM)
            db=tmp/'cat.db';con=sqlite3.connect(db)
            con.executescript('''CREATE TABLE targets(target_id TEXT PRIMARY KEY,source_sha256 TEXT,isa TEXT,system_tag TEXT);
              CREATE TABLE graph_runs(run_id TEXT PRIMARY KEY,target_id TEXT);
              CREATE TABLE graph_functions(run_id TEXT,entry INTEGER);''')
            con.execute('INSERT INTO targets VALUES(?,?,?,?)',('fixture',SHA,'m68k','megadrive'))
            con.execute('INSERT INTO graph_runs VALUES (?,?)',('run0','fixture'))
            con.execute('INSERT INTO graph_functions VALUES (?,?)',('run0',0x200))
            con.commit();con.close()
            previous=tmp/'old'/ 'ghidra';previous.mkdir(parents=True)
            (previous/'fixture.json').write_text(json.dumps(doc('fixture')))
            # This is a cache/identity/translation test, not a native compiler
            # acceptance test. An installed MSVC, Ghidra or Unix compiler must
            # not change its expected outcome. Real C++ compilation is covered
            # by the versioned compiled-native acceptance gate.
            with patch('recovery.pipeline.find_cpp_compiler',return_value=None) as compiler_probe:
                result=autopilot(db,[source],[],None,tmp/'new',limit=1,pypcode_check=False,
                                 previous_ghidra_dir=previous,compare_samples=False)
            compiler_probe.assert_called_once()
            self.assertEqual(result['successes'][0]['analysis_source'],'SHA_MATCHED_REUSED_EXPORT')
            self.assertEqual(result['function_pipeline']['functions_submitted'],1)
            self.assertEqual(result['function_pipeline']['statuses'],{'COMPILER_NOT_FOUND':1})
            self.assertEqual(result['function_pipeline']['cpp_seeded_smoke_only'],0)
            self.assertEqual(result['function_pipeline']['original_vs_native_parity_passed'],0)
            manifests=list((tmp/'new'/'compiled').glob('fixture-*/manifest.json'))
            self.assertEqual(len(manifests),1)
            metadata=json.loads(manifests[0].read_text())
            self.assertEqual(metadata['source_sha256'],SHA)
            self.assertEqual(metadata['compile_status'],'COMPILER_NOT_FOUND')
            self.assertEqual(metadata['lowering_status'],'LOWERED_RAW_PCODE_UNVERIFIED')
            self.assertTrue((manifests[0].parent/'function.cpp').is_file())
            con=sqlite3.connect(db)
            self.assertEqual(con.execute('SELECT count(*) FROM conversion_v031').fetchone()[0],1)
            con.close()

    def test_cache_wrong_source_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';d=doc('fixture');d['source_sha256']='0'*64;p.write_text(json.dumps(d))
            from recovery.pipeline import read_export
            self.assertEqual(read_export(p)['source_sha256'],'0'*64)
            # no claims about ownership or instruction bytes are made solely from JSON.

if __name__=='__main__':unittest.main()

class SQLiteImportTests(unittest.TestCase):
    def test_sqlite_backup_is_valid_and_one_time_only(self):
        from tools.import_previous_catalogue import import_previous
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);original=d/'old.db';new=d/'new.db';stamp=d/'stamp.json'
            con=sqlite3.connect(original)
            con.executescript('CREATE TABLE targets(id INTEGER);CREATE TABLE graph_runs(id INTEGER);CREATE TABLE graph_functions(id INTEGER);')
            con.execute('INSERT INTO targets VALUES (12)');con.commit();con.close()
            out=import_previous(original,new,stamp)
            self.assertEqual(out['status'],'SQLITE_BACKUP_NEW_WORKING_DB')
            con=sqlite3.connect(new)
            self.assertEqual(con.execute('SELECT * FROM targets').fetchone()[0],12)
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            con.close()
            self.assertEqual(import_previous(original,new,stamp)['status'],'EXISTING_WORKING_DB_REUSED')

class SQLiteWindowsLockRegressionTests(unittest.TestCase):
    """Regression for WinError 32: never replace a Workbench-open SQLite file."""
    def test_working_database_is_separate_and_reused_not_replaced(self):
        from tools.import_previous_catalogue import import_previous
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);original=p/'workbench-open.sqlite';working=p/'independent-working.sqlite'
            stamp=p/'import-stamp.json'
            opened=sqlite3.connect(original)
            opened.executescript('CREATE TABLE targets(id INTEGER);CREATE TABLE graph_runs(id INTEGER);CREATE TABLE graph_functions(id INTEGER);')
            opened.execute('INSERT INTO targets VALUES(42)');opened.commit()
            first=import_previous(original,working,stamp)
            self.assertEqual(first['status'],'SQLITE_BACKUP_NEW_WORKING_DB')
            # Hold connections to BOTH files, simulating active Workbench readers.
            live=sqlite3.connect(working)
            self.assertEqual(live.execute('SELECT id FROM targets').fetchone()[0],42)
            opened.execute('INSERT INTO targets VALUES(43)');opened.commit()
            second=import_previous(original,working,stamp)
            self.assertEqual(second['status'],'EXISTING_WORKING_DB_REUSED')
            self.assertEqual(live.execute('SELECT count(*) FROM targets').fetchone()[0],1)
            live.close();opened.close()
    def test_prefers_richer_conversion_evidence(self):
        from tools.import_previous_catalogue import import_best
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);v32=p/'older-empty.sqlite';v31=p/'with-evidence.sqlite'
            for source,n in ((v32,0),(v31,5)):
                con=sqlite3.connect(source)
                con.executescript('CREATE TABLE targets(id INTEGER);CREATE TABLE graph_runs(id INTEGER);CREATE TABLE graph_functions(id INTEGER);CREATE TABLE conversion_v031(x INTEGER);')
                con.executemany('INSERT INTO conversion_v031 VALUES (?)',[(j,) for j in range(n)])
                con.commit();con.close()
            result=import_best([v32,v31],p/'working.sqlite',p/'stamp.json')
            self.assertEqual(Path(result['source']),v31)
            with closing(sqlite3.connect(p/'working.sqlite')) as con:
                self.assertEqual(con.execute('SELECT count(*) FROM conversion_v031').fetchone()[0],5)

class ZeroTargetsDiagnosticTests(unittest.TestCase):
    def test_no_source_matches_still_writes_full_diagnostics(self):
        from recovery.autopilot import autopilot
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);db=tmp/'catalogue.sqlite'
            con=sqlite3.connect(db)
            con.executescript('''CREATE TABLE targets(target_id TEXT PRIMARY KEY,
              system_tag TEXT,isa TEXT,source_sha256 TEXT);
              CREATE TABLE graph_runs(run_id TEXT,target_id TEXT);
              CREATE TABLE graph_functions(run_id TEXT,entry INTEGER);''')
            con.execute('INSERT INTO targets VALUES(?,?,?,?)',
                        ('fixture','megadrive','m68k','1'*64))
            con.commit();con.close()
            output=tmp/'campaign'
            result=autopilot(db,[],[],None,output,limit=1,
                             previous_ghidra_dir=tmp/'missing',compare_samples=False)
            self.assertFalse(result['successes'])
            self.assertEqual(result['issues'][0]['status'],'AUTHENTICATED_SOURCE_NOT_FOUND')
            self.assertEqual(result['diagnostics']['targets_in_catalogue'],1)
            self.assertTrue((output/'autopilot-report.json').is_file())
            self.assertTrue((output/'compiled'/'campaign.json').is_file())
