"""No real game ROMs included; fixtures test compiler/boundary guards, NOT CPU parity."""
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.formats import open_image
from recovery.codegen import generate,Blocked
from recovery.pipeline import check_source_bytes,read_export,run

ROM=bytearray(0x400)
ROM[0x100:0x104]=b'SEGA';ROM[4:8]=(0x200).to_bytes(4,'big')
ROM[0x200:0x204]=bytes.fromhex('70054e75')
SHA=hashlib.sha256(ROM).hexdigest()

def instruction(addr,n,b,code,flow=None):
    return dict(address=addr,length=n,bytes_sha256=hashlib.sha256(b).hexdigest(),
       mnemonic='MOVEQ' if addr==0x200 else 'RTS',delay_slots=0,call=False,
       terminal=addr==0x202,flows=[],fallthrough=flow,pcode=code)

D0={'space':'register','offset':0,'size':4,'name':'D0'}
CON5={'space':'const','offset':5,'size':4,'name':None}
A7={'space':'register','offset':28,'size':4,'name':'A7'}
FUNCTION={'entry':0x200,'name':'synthetic_fixture','instructions':[
    instruction(0x200,2,bytes.fromhex('7005'),[{'op':'COPY','output':D0,'inputs':[CON5]}],0x202),
    instruction(0x202,2,bytes.fromhex('4e75'),[{'op':'RETURN','output':None,'inputs':[A7]}]),
]}

def doc(tid):return dict(schema='recomp-function-pcode-v1',target_id=tid,source_sha256=SHA,
   analyzer='ghidra-raw-pcode',language='68000:BE:32:default',functions=[FUNCTION])

class TestRecovery(unittest.TestCase):
    def test_byte_mapping_and_source_validation(self):
        image=open_image(bytes(ROM),'megadrive')
        self.assertEqual(check_source_bytes(FUNCTION,image),'')
        altered=json.loads(json.dumps(FUNCTION));altered['instructions'][0]['bytes_sha256']='0'*64
        self.assertEqual(check_source_bytes(altered,image),'GHIDRA_BYTES_DIFFER_FROM_AUTHENTICATED_SOURCE')
    def test_unimplemented_semantics_always_block(self):
        f=json.loads(json.dumps(FUNCTION));f['instructions'][0]['pcode'][0]['op']='FLOAT_NAN'
        with self.assertRaisesRegex(Blocked,'unsupported_pcode'):generate(f,'m68k','68000:BE:32:default')
    def test_no_partial_branch_or_call(self):
        f=json.loads(json.dumps(FUNCTION));f['instructions'][0]['call']=True
        with self.assertRaisesRegex(Blocked,'external_call'):generate(f,'m68k','68000:BE:32:default')
        f['instructions'][0]['call']=False;f['instructions'][0]['fallthrough']=0x300
        with self.assertRaisesRegex(Blocked,'fallthrough_outside'):generate(f,'m68k','68000:BE:32:default')
    def test_unsupported_mips_delay(self):
        f=json.loads(json.dumps(FUNCTION));f['instructions'][0]['delay_slots']=1
        with self.assertRaisesRegex(Blocked,'delay_slot'):generate(f,'mips','MIPS:LE:32:default')
    def test_compiler_executes_pcode_fixture(self):
        compiler=shutil.which('g++') or shutil.which('clang++')
        if not compiler:self.skipTest('C++ compiler not installed')
        code=generate(FUNCTION,'m68k','68000:BE:32:default')
        with tempfile.TemporaryDirectory() as d:
            cpp=Path(d)/'f.cpp';cpp.write_text(code['cpp'],encoding='utf-8')
            from recovery.pipeline import compile_cpp
            status,detail=compile_cpp(cpp,compiler)
            self.assertEqual(status,'COMPILED_RUNNER_SMOKE_ONLY',detail)
            import subprocess
            r=subprocess.run([str(cpp.with_suffix(''))],capture_output=True,text=True,check=True)
            self.assertIn('D0 0 4 5',r.stdout)
    def test_integrated_campaign_on_sha_matched_synthetic_file(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);src=d/'fixture.md';src.write_bytes(ROM)
            db=d/'fixture.db';con=sqlite3.connect(db)
            con.executescript('''CREATE TABLE targets(target_id TEXT PRIMARY KEY,source_sha256 TEXT,isa TEXT,system_tag TEXT);
            CREATE TABLE graph_runs(run_id TEXT PRIMARY KEY,target_id TEXT);
            CREATE TABLE graph_functions(run_id TEXT,entry INTEGER);''')
            con.execute('INSERT INTO targets VALUES (?,?,?,?)',('megadrive-fixture',SHA,'m68k','megadrive'))
            con.execute('INSERT INTO graph_runs VALUES (?,?)',('r0','megadrive-fixture'))
            con.execute('INSERT INTO graph_functions VALUES (?,?)',('r0',0x200));con.commit();con.close()
            exp=d/'ghidra.json';exp.write_text(json.dumps(doc('megadrive-fixture')),encoding='utf-8')
            out=run(db,[src],(),[exp],d/'generated',10,compile_native=False)
            self.assertEqual(out['functions_submitted'],1)
            self.assertEqual(out['statuses'],{'CPP_EMITTED_NOT_COMPILED':1})
            self.assertEqual(out['original_vs_native_parity_passed'],0)
            con=sqlite3.connect(db)
            self.assertEqual(con.execute('SELECT count(*) FROM conversion_v031').fetchone()[0],1);con.close()
            self.assertTrue((next((d/'generated').glob('megadrive-fixture-00000200-*/function.cpp'))).is_file())

if __name__=='__main__':unittest.main()

class TestSemanticsExtra(unittest.TestCase):
    def compile_run(self, f, *argv):
        compiler=shutil.which('g++') or shutil.which('clang++')
        if not compiler:self.skipTest('C++ compiler not installed')
        from recovery.pipeline import compile_cpp
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'p.cpp'
            path.write_text(generate(f,'m68k','68000:BE:32:default')['cpp'],encoding='utf-8')
            status,reason=compile_cpp(path,compiler)
            self.assertEqual(status,'COMPILED_RUNNER_SMOKE_ONLY',reason)
            result=subprocess.run([str(path.with_suffix('')),*argv],capture_output=True,text=True,check=True)
            return result.stdout
    def test_big_endian_subregister_alias(self):
        f=json.loads(json.dumps(FUNCTION))
        low={'space':'register','offset':3,'size':1,'name':'D0B'}
        f['instructions'][0]['pcode']=[{'op':'COPY','inputs':[{'space':'const','offset':0xaa,'size':1}], 'output':low}]
        result=self.compile_run(f,'0:4:0x11223344')
        self.assertIn('D0B 3 1 170',result)
    def test_unsigned_addition_wraps_exact_width(self):
        f=json.loads(json.dumps(FUNCTION))
        f['instructions'][0]['pcode']=[{'op':'INT_ADD','inputs':[D0,{'space':'const','offset':1,'size':4}],'output':D0}]
        result=self.compile_run(f,'0:4:4294967295')
        self.assertIn('D0 0 4 0',result)
    def test_branch_taken_and_fallthrough(self):
        f=json.loads(json.dumps(FUNCTION))
        f['instructions'].insert(1,instruction(0x204,2,b'\x4e\x71',[{'op':'COPY','inputs':[CON5],'output':D0}],0x202))
        f['instructions'][0]['pcode']=[{'op':'CBRANCH',
            'inputs':[{'space':'ram','offset':0x204,'size':4},{'space':'const','offset':1,'size':1}], 'output':None}]
        # The taken path writes D0=5 and falls into RTS; the false path goes directly to RTS.
        self.assertIn('D0 0 4 5',self.compile_run(f))
    def test_unqualified_memory_space_is_blocked(self):
        f=json.loads(json.dumps(FUNCTION))
        f['instructions'][0]['pcode']=[{'op':'LOAD',
           'inputs':[{'space':'const','offset':0,'size':4},A7],'output':D0}]
        with self.assertRaisesRegex(Blocked,'memory_space_not_qualified'):
            generate(f,'m68k','68000:BE:32:default')
    def test_workbench_v031_endpoint_without_campaign(self):
        from workbench import data
        with tempfile.TemporaryDirectory() as d:
            con=sqlite3.connect(str(Path(d)/'c.db'));con.row_factory=sqlite3.Row
            ret=data(con,'functions-v031',{})
            self.assertEqual(ret['jobs'],[]);con.close()
