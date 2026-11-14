#!/usr/bin/env python3
"""No gameplay, no ROM license needed: independent 3-ISA offline fixtures."""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.engine import interrogate,AnalysisFailure,registry,_plugin
from offline_analysis.plugins import cpu_z80,cpu_m68k,cpu_mips
from offline_analysis.model import Unresolved

class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rd-v35-offline-')
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
    def write(self,name,data):
        p=self.home/name;p.write_bytes(data);return p
    def scan(self,name,data,**opts):
        p=self.write(name,data)
        report=interrogate(p,self.home/(name+'.evidence'),**opts)
        return p,report,self.home/(name+'.evidence')
    def sms(self,banks=4):
        a=bytearray(b'\xff'*(0x4000*banks));a[0x7ff0:0x7ff8]=b'TMR SEGA'
        a[0:3]=b'\xc3\x00\x01' # JP 0100
        a[0x38]=a[0x66]=0xc9
        return a
    def md(self):
        a=bytearray(0x1000);a[:4]=(0xfff000).to_bytes(4,'big')
        a[4:8]=(0x200).to_bytes(4,'big')
        a[0x100:0x104]=b'SEGA';a[0x200:0x204]=bytes.fromhex('4e 71 60 fc')
        return a
    def psx(self):
        a=bytearray(0x800+0x100);a[:8]=b'PS-X EXE'
        a[0x10:0x14]=(0x80010000).to_bytes(4,'little')
        a[0x18:0x1c]=(0x80010000).to_bytes(4,'little')
        a[0x1c:0x20]=(0x100).to_bytes(4,'little')
        a[0x800:0x804]=(0x08004000).to_bytes(4,'little') # J self
        a[0x804:0x808]=b'\0\0\0\0' # Delay slot
        return a
    def test_sms_banked_discovery_without_gameplay(self):
        a=self.sms()
        # Initialize stack; write a bank-register constant; JP to new bank.
        a[0x100:0x10b]=bytes.fromhex('31 00 d0 3e 03 32 fe ff c3 00 40')
        a[3*0x4000:3*0x4000+3]=bytes.fromhex('3e 2a c9')
        p,r,out=self.scan('fixture.sms',a)
        self.assertEqual(r['profile'],'sega-master-system')
        self.assertEqual(r['cpu'],'z80')
        ins=json.loads((out/'instructions.json').read_text())
        self.assertTrue(any(x['pc']==0x4000 and x['physical']==3*0x4000 for x in ins))
        self.assertEqual(len(json.loads((out/'bank-inventory.json').read_text())),4)
        self.assertFalse(r['native_compilation_performed'])
        self.assertFalse(r['whole_game_code_coverage_qualified'])
        self.assertEqual(p.read_bytes(),a)
    def test_sms_unknown_bank_not_claimed(self):
        a=self.sms();a[0x100:0x108]=bytes.fromhex('31 00 d0 32 fe ff c3 00')
        a[0x108]=0x40
        _,r,out=self.scan('unknown-bank.sms',a)
        self.assertIn('ROM_BANK_CONTEXT_UNRESOLVED',
                      [x['reason'] for x in json.loads((out/'unresolved.json').read_text())])
    def test_sms_indirect_jump_remains_gap(self):
        a=self.sms();a[0x100]=0xe9
        _,r,out=self.scan('indirect.sms',a)
        self.assertIn('INDIRECT_TARGET_UNRESOLVED',
                      [x['reason'] for x in json.loads((out/'unresolved.json').read_text())])
    def test_bank_inventory_all_source_banks(self):
        a=self.sms(16);a[0x100:0x102]=b'\x18\xfe'
        _,r,out=self.scan('sixteen.sms',a)
        self.assertEqual(len(json.loads((out/'bank-inventory.json').read_text())),16)
        self.assertEqual(r['possible_orphan_entries'],26)
        self.assertLess(r['static_candidate_bytes'],len(a))
        self.assertFalse(r['standalone_export_ready'])
    def test_md_recognised_own_cpu_and_memory_plugin(self):
        _,r,out=self.scan('game.bin',self.md())
        self.assertEqual(r['profile'],'sega-mega-drive')
        self.assertEqual(r['cpu'],'m68000')
        ins=json.loads((out/'instructions.json').read_text())
        self.assertEqual({x['pc'] for x in ins},{0x200,0x202})
        self.assertEqual(r['unresolved'],0)
    def test_md_unrecognised_opcode_fails_closed(self):
        a=self.md();a[0x200:0x202]=b'\x48\xe7' # MOVEM, variable-length unsupported
        _,r,out=self.scan('unsupported.bin',a)
        self.assertEqual(r['status'],'ANALYSED_PARTIAL')
        self.assertFalse(json.loads((out/'instructions.json').read_text()))
        self.assertIn('M68000_INSTRUCTION_LENGTH_UNVERIFIED',
                      [x['reason'] for x in json.loads((out/'unresolved.json').read_text())])
    def test_psx_entry_branch_and_delay_slot(self):
        _,r,out=self.scan('main.exe',self.psx())
        self.assertEqual(r['profile'],'sony-psx-exe')
        self.assertEqual(r['cpu'],'mips-r3000a')
        ins=json.loads((out/'instructions.json').read_text())
        self.assertEqual({x['pc'] for x in ins},{0x80010000,0x80010004})
        self.assertEqual(r['unresolved'],0)
        self.assertFalse(r['semantic_parity_qualified'])
    def test_psx_invalid_entry_is_unsupported(self):
        a=self.psx();a[0x10:0x14]=(0x90010000).to_bytes(4,'little')
        _,r,out=self.scan('bad.exe',a)
        self.assertEqual(r['status'],'UNSUPPORTED_FORMAT')
        self.assertEqual(json.loads((out/'instructions.json').read_text()),[])
    def test_mips_unknown_opcode_reported(self):
        a=self.psx();a[0x800:0x804]=(0xfc000000).to_bytes(4,'little')
        _,r,out=self.scan('badop.exe',a)
        self.assertEqual(r['status'],'ANALYSED_PARTIAL')
        self.assertFalse(json.loads((out/'instructions.json').read_text()))
    def test_unknown_input_still_gets_portable_report(self):
        _,r,out=self.scan('unknown.rom',b'random foreign data'*1024)
        self.assertEqual(r['status'],'UNSUPPORTED_FORMAT')
        self.assertEqual(len(r['supported_profiles']),3)
        self.assertTrue((out/'analysis.json').is_file())
    def test_never_reinterpret_extension(self):
        _,r,_=self.scan('fake.sms',self.md())
        self.assertEqual(r['profile'],'sega-mega-drive')
    def test_no_overwrite_or_source_mutation(self):
        a=self.sms();p,r,out=self.scan('safe.sms',a)
        with self.assertRaisesRegex(AnalysisFailure,'OUTPUT_EXISTS_REFUSING_OVERWRITE'):
            interrogate(p,out)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),r['source_sha256'])
    def test_source_symlink_refused(self):
        a=self.sms();p=self.write('src.sms',a)
        alias=self.home/'alias.sms'
        try:alias.symlink_to(p)
        except (OSError,NotImplementedError):
            self.skipTest('OS forbids unprivileged symlink creation')
        with self.assertRaisesRegex(AnalysisFailure,'REGULAR_SOURCE_FILE_REQUIRED'):
            interrogate(alias,self.home/'other')
    def test_invalid_plugin_rejected(self):
        with self.assertRaisesRegex(AnalysisFailure,'PROVIDER_MODULE_OUTSIDE_REGISTERED_NAMESPACE'):
            _plugin('os.system')
    def test_registry_ids_unique(self):
        self.assertEqual([p['id'] for p in registry()],
                         ['sega-master-system','sega-mega-drive','sony-psx-exe'])
    def test_cli_portable_exit_codes(self):
        p=self.write('unknown.rom',b'not a console')
        cmd=[sys.executable,str(ROOT/'offline_analysis'/'cli.py'),'--rom',str(p),
             '--out',str(self.home/'report')]
        run=subprocess.run(cmd,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,2,run.stderr)
        self.assertIn('UNSUPPORTED_FORMAT',run.stdout)
    def test_manifest_artifact_integrity(self):
        _,r,out=self.scan('integrity.bin',self.md())
        for x in r['artifacts'].values():
            b=(out/x['file']).read_bytes()
            self.assertEqual(len(b),x['bytes'])
            self.assertEqual(hashlib.sha256(b).hexdigest(),x['sha256'])
    def test_instruction_length_strictness(self):
        self.assertEqual(cpu_z80.decode(lambda pc,n:b'\x21\x00\xc0'[:n],0).length,3)
        self.assertEqual(cpu_m68k.decode(lambda pc,n:b'\x4e\x71'[:n],0).length,2)
        self.assertEqual(cpu_mips.decode(lambda pc,n:b'\x00\x00\x00\x00'[:n],0).length,4)
        with self.assertRaises(Unresolved):cpu_m68k.decode(lambda pc,n:b'\x48\xe7'[:n],0)

if __name__=='__main__':unittest.main(verbosity=2)
