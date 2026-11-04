"""Real observed failing addresses, but synthetic instruction fixtures: not ROM parity."""
from contextlib import closing

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovery.codegen import generate
from recovery.pipeline import compile_cpp, seeded_runner_args
from test_function_v031 import FUNCTION,D0

CONST=lambda n,w:{'space':'const','offset':n,'size':w}
RAM=lambda n,w:{'space':'ram','offset':n,'size':w}

class MegaDriveBusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler=shutil.which('g++') or shutil.which('clang++')
        if not cls.compiler:raise unittest.SkipTest('No native C++ compiler')

    def run_code(self,operations,flags=None, image=None):
        f=json.loads(json.dumps(FUNCTION))
        f['instructions'][0]['pcode']=operations
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); cpp=td/'fixture.cpp'
            cpp.write_text(generate(f,'m68k','68000:BE:32:default')['cpp'])
            args=['--megadrive-bus',*(flags or [])]
            if image is not None:
                rom=td/'game.md';rom.write_bytes(image)
                args=['--image',str(rom),'0','0',str(len(image)),*args]
            status,detail=compile_cpp(cpp,self.compiler,runner_args=args)
            result=subprocess.run([str(cpp.with_suffix('')),*args],text=True,capture_output=True)
            return status,detail,result

    def test_24bit_sign_extended_work_ram_address(self):
        addr=0xfffff00b   # Ghidra 32-bit address maps to physical FF:F00B
        ops=[{'op':'COPY','inputs':[CONST(0x7a,1)],'output':RAM(addr,1)},
             {'op':'COPY','inputs':[RAM(0xfff00b,1)],'output':D0}]
        status,detail,r=self.run_code(ops)
        self.assertEqual(status,'COMPILED_SEEDED_SMOKE_ONLY',detail)
        self.assertIn('MEM 16773131 1 122',r.stdout)   # 0xFFF00B
        self.assertIn('D0 0 4 122',r.stdout)

    def test_work_ram_mirror_e00000(self):
        ops=[{'op':'COPY','inputs':[CONST(0x5a,1)],'output':RAM(0xe00020,1)},
             {'op':'COPY','inputs':[RAM(0xff0020,1)],'output':D0}]
        status,detail,r=self.run_code(ops)
        self.assertEqual(status,'COMPILED_SEEDED_SMOKE_ONLY',detail)
        self.assertIn(f'MEM {0xff0020} 1 90',r.stdout)
        self.assertIn('D0 0 4 90',r.stdout)

    def test_vdp_control_word_is_trace_only(self):
        ops=[{'op':'COPY','inputs':[CONST(0x8174,2)],'output':RAM(0xc00004,2)}]
        status,detail,r=self.run_code(ops)
        self.assertEqual(status,'COMPILED_HARDWARE_TRACE_SMOKE_ONLY',detail)
        self.assertIn('IO VDP_CONTROL 12582916 2 33140',r.stdout)
        self.assertNotIn('MEM 12582916',r.stdout)

    def test_psg_controller_and_z80_event_trace_order(self):
        ops=[{'op':'COPY','inputs':[CONST(0x9f,1)],'output':RAM(0xc00011,1)},
             {'op':'COPY','inputs':[CONST(0x40,1)],'output':RAM(0xa10009,1)},
             {'op':'COPY','inputs':[CONST(0x100,2)],'output':RAM(0xa11100,2)}]
        status,detail,r=self.run_code(ops)
        self.assertEqual(status,'COMPILED_HARDWARE_TRACE_SMOKE_ONLY',detail)
        self.assertEqual([l.split(' ')[1] for l in r.stdout.splitlines() if l.startswith('IO ')],
                         ['PSG','CONTROLLER_IO','Z80_BUSREQ'])

    def test_bad_width_vdp_write_remains_blocked(self):
        ops=[{'op':'COPY','inputs':[CONST(0x12,1)],'output':RAM(0xc00004,1)}]
        status,detail,r=self.run_code(ops)
        self.assertEqual(status,'COMPILED_SEEDED_RUNTIME_FAILED')
        self.assertIn('unqualified hardware write',r.stderr)

    def test_hardware_read_is_unqualified_not_zero(self):
        ops=[{'op':'COPY','inputs':[RAM(0xc00004,2)],'output':D0}]
        status,detail,r=self.run_code(ops)
        self.assertEqual(status,'COMPILED_SEEDED_RUNTIME_FAILED')
        self.assertIn('unmodelled hardware read',r.stderr)

    def test_rom_write_is_not_silent_success(self):
        ops=[{'op':'COPY','inputs':[CONST(7,2)],'output':RAM(0x84,2)}]
        status,detail,r=self.run_code(ops,image=bytes(0x300))
        self.assertEqual(status,'COMPILED_SEEDED_RUNTIME_FAILED')
        self.assertIn('ROM memory write at 132',r.stderr)

    def test_explicit_fixture_cannot_seed_rom(self):
        ops=[{'op':'COPY','inputs':[CONST(1,4)],'output':D0}]
        status,detail,r=self.run_code(ops,flags=['m:0:1:5'])
        self.assertEqual(status,'COMPILED_SEEDED_RUNTIME_FAILED')
        self.assertIn('fixture cannot seed non-RAM',r.stderr)

    def test_legacy_sparse_bus_does_not_allow_unmapped_hardware(self):
        ops=[{'op':'COPY','inputs':[CONST(1,2)],'output':RAM(0xc00004,2)}]
        status,detail,r=self.run_code(ops,flags=[],image=None)
        self.assertEqual(status,'COMPILED_HARDWARE_TRACE_SMOKE_ONLY',detail)

if __name__=='__main__':unittest.main()

class CampaignHardwareEvidenceTests(unittest.TestCase):
    def test_hardware_trace_persisted_and_not_compared_as_parity(self):
        import hashlib,sqlite3
        from recovery.autopilot import autopilot
        from test_function_v031 import ROM, SHA,doc
        if not (shutil.which('g++') or shutil.which('clang++')):
            self.skipTest('no native C++ compiler')
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp); src=home/'fixture.md';src.write_bytes(ROM)
            db=home/'catalogue.sqlite'
            with closing(sqlite3.connect(db)) as con, con:
                con.executescript('''CREATE TABLE targets(target_id TEXT PRIMARY KEY,source_sha256 TEXT,isa TEXT,system_tag TEXT);
                CREATE TABLE graph_runs(run_id TEXT PRIMARY KEY,target_id TEXT);
                CREATE TABLE graph_functions(run_id TEXT,entry INTEGER);''')
                con.execute('INSERT INTO targets VALUES(?,?,?,?)',('fixture',SHA,'m68k','megadrive'))
                con.execute('INSERT INTO graph_runs VALUES(?,?)',('run0','fixture'))
                con.execute('INSERT INTO graph_functions VALUES(?,?)',('run0',0x200))
            cached=home/'cached';cached.mkdir()
            original=doc('fixture')
            original['functions'][0]['instructions'][0]['pcode']=[
                {'op':'COPY','inputs':[CONST(0x8174,2)],'output':RAM(0xc00004,2)}]
            (cached/'fixture.json').write_text(json.dumps(original))
            out=home/'run'
            result=autopilot(db,[src],[],None,out,limit=1,
                             previous_ghidra_dir=cached,pypcode_check=False,compare_samples=True)
            p=result['function_pipeline']
            self.assertEqual(p['cpp_hardware_trace_smoke_only'],1)
            self.assertEqual(p['sample_comparisons_attempted'],0)
            self.assertEqual(p['hardware_trace_reference_not_attempted'],1)
            self.assertEqual(p['jobs'][0]['verification_status'],'HARDWARE_EVENT_TRACE_ONLY_NOT_CPU_PARITY')
            folder=next((out/'compiled').glob('fixture-00000200-*'))
            smoke=json.loads((folder/'native-smoke.json').read_text())
            self.assertEqual(smoke['hardware_event_count'],1)
            self.assertIn('IO VDP_CONTROL 12582916 2 33140',smoke['hardware_event_lines'])
            manifest=json.loads((folder/'manifest.json').read_text())
            self.assertEqual(manifest['native_smoke_evidence'],'native-smoke.json')
            self.assertEqual(manifest['verification_status'],'HARDWARE_EVENT_TRACE_ONLY_NOT_CPU_PARITY')
            self.assertEqual(p['original_vs_native_parity_passed'],0)
