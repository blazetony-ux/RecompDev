"""v0.4.9.18 no-external-tool analysis reuse and tamper refusal."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_integration.analysis_reuse import cache_contract, record_cache_contract, reuse_initial
from analysis_integration.providers import ProviderBlocked
from analysis_integration.reconciliation import reconcile

def sha(data): return hashlib.sha256(data).hexdigest()

class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.rom=self.root/'game.sms'
        self.rom.write_bytes(b'\x00' * 0x10000)
        self.toolroot=self.root/'tools';self.toolroot.mkdir()
        self.gh=self.toolroot/'analyzeHeadless.bat';self.gh.write_bytes(b'fixture ghidra')
        self.old=self.root/'old';self.analysis=self.old/'analysis';self.analysis.mkdir(parents=True)
        contract=cache_contract(self.rom,self.gh,None,(self.toolroot,))
        doc={'schema':'recomp-function-pcode-v1','analyzer':'ghidra-raw-pcode',
             'language':'z80:LE:16:default','source_sha256':sha(self.rom.read_bytes()),
             'functions':[{'entry':0,'body_min':0,'body_max':0,'instructions':[
                 {'address':0,'length':1,'bytes_sha256':sha(b'\x00')}]}]}
        p=self.analysis/'ghidra-functions.json';p.write_text(json.dumps(doc),encoding='utf8')
        self.anal={'schema':'recompdev.analysis.providers.v1','source_sha256':sha(self.rom.read_bytes()),
                   'ghidra_export_sha256':sha(p.read_bytes()),'ghidra_verified_functions':1,
                   'ghidra_verified_instructions':1,'ghidra_execution':{'tool_sha256':sha(self.gh.read_bytes())},
                   'reconciliation_sha256':None,'external_tools_executed':['ghidra']}
        record_cache_contract(self.anal,self.analysis,contract)
        (self.old/'orchestration.json').write_text(json.dumps({'schema':'recompdev.native.orchestrator.v1',
            'source_sha256':sha(self.rom.read_bytes()),'analysis':self.anal,'rounds':[{'round':1}]}))

    def reuse(self,folder='new'):
        return reuse_initial(self.old,self.rom,self.root/folder,ghidra=self.gh,rizin=None,roots=(self.toolroot,))

    def test_reuse_is_immutable_source_and_tool_checked(self):
        original=(self.analysis/'ghidra-functions.json').read_bytes()
        gh,rz,doc=self.reuse()
        self.assertIsNone(rz)
        self.assertEqual(original,gh.read_bytes())
        self.assertEqual(doc['cache_reuse'],'SOURCE_TOOL_PROVIDER_ATTESTED')
        self.assertEqual(doc['external_tools_executed'],[])
        self.assertEqual(original,(self.analysis/'ghidra-functions.json').read_bytes())

    def test_modified_ir_fails_closed(self):
        (self.analysis/'ghidra-functions.json').write_text('{"forged":true}')
        with self.assertRaisesRegex(ProviderBlocked,'ARTIFACT_HASH_MISMATCH'):self.reuse()

    def test_tool_change_forces_fresh_analysis_not_reuse(self):
        self.gh.write_bytes(b'updated ghidra')
        self.assertIsNone(self.reuse())
        self.assertFalse((self.root/'new').exists())

    def test_changed_original_rom_is_rejected(self):
        self.rom.write_bytes(b'\x01'+b'\x00'*(0x10000-1))
        with self.assertRaisesRegex(ProviderBlocked,'ROM_IDENTITY_MISMATCH'):self.reuse()

    def test_rizin_reconciliation_is_recomputed_without_subprocess(self):
        rztool=self.toolroot/'rizin.exe';rztool.write_bytes(b'rizin-fixture')
        rzfile=self.analysis/'rizin/rizin-aflj.json';rzfile.parent.mkdir()
        rzfile.write_text(json.dumps([{'offset':0,'size':1,'name':'fcn.0'}]))
        gh=self.analysis/'ghidra-functions.json'
        rec=self.analysis/'reconciled-functions.json'
        # Force Windows-style CRLF regardless of the host OS: source
        # reconciliation must reuse original signed-by-hash reports unchanged.
        rendered=json.dumps(reconcile(self.rom,0,'z80',gh,rzfile),indent=2,sort_keys=True)+'\n'
        rec.write_bytes(rendered.replace('\n','\r\n').encode('utf-8'))
        self.anal['rizin_execution']={'export_sha256':sha(rzfile.read_bytes()),'tool_sha256':sha(rztool.read_bytes())}
        self.anal['reconciliation_sha256']=sha(rec.read_bytes())
        contract=cache_contract(self.rom,self.gh,rztool,(self.toolroot,))
        record_cache_contract(self.anal,self.analysis,contract)
        (self.old/'orchestration.json').write_text(json.dumps({'schema':'recompdev.native.orchestrator.v1',
            'source_sha256':sha(self.rom.read_bytes()),'analysis':self.anal,'rounds':[{'round':1}]}))
        export,recon,result=reuse_initial(self.old,self.rom,self.root/'new',ghidra=self.gh,rizin=rztool,roots=(self.toolroot,))
        self.assertEqual(recon.read_bytes(),rec.read_bytes())
        self.assertEqual(result['external_tools_executed'],[])
        rec.write_text('[]')
        with self.assertRaisesRegex(ProviderBlocked,'ARTIFACT_HASH_MISMATCH'):
            reuse_initial(self.old,self.rom,self.root/'bad',ghidra=self.gh,rizin=rztool,roots=(self.toolroot,))

    def test_lf_and_crlf_reconciliation_reuse_is_byte_preserving(self):
        rztool=self.toolroot/'rizin.exe';rztool.write_bytes(b'rizin-fixture')
        rzfile=self.analysis/'rizin/rizin-aflj.json';rzfile.parent.mkdir()
        rzfile.write_text(json.dumps([{'offset':0,'size':1,'name':'fcn.0'}]),encoding='utf-8')
        gh=self.analysis/'ghidra-functions.json'
        rec=self.analysis/'reconciled-functions.json'
        rendered=json.dumps(reconcile(self.rom,0,'z80',gh,rzfile),indent=2,sort_keys=True)+'\n'
        for newline, folder in (('\n','lf'), ('\r\n','crlf')):
            rec.write_bytes(rendered.replace('\n',newline).encode('utf-8'))
            original=rec.read_bytes()
            self.anal['rizin_execution']={'export_sha256':sha(rzfile.read_bytes()),'tool_sha256':sha(rztool.read_bytes())}
            self.anal['reconciliation_sha256']=sha(original)
            contract=cache_contract(self.rom,self.gh,rztool,(self.toolroot,))
            record_cache_contract(self.anal,self.analysis,contract)
            (self.old/'orchestration.json').write_text(json.dumps({
                'schema':'recompdev.native.orchestrator.v1',
                'source_sha256':sha(self.rom.read_bytes()),
                'analysis':self.anal,'rounds':[{'round':1}]}),encoding='utf-8')
            _,copied,_=reuse_initial(self.old,self.rom,self.root/folder,
                ghidra=self.gh,rizin=rztool,roots=(self.toolroot,))
            self.assertEqual(copied.read_bytes(),original)
            self.assertEqual(rec.read_bytes(),original)

    def test_old_pre_cache_report_falls_back_to_fresh(self):
        doc=json.loads((self.old/'orchestration.json').read_text())
        doc['analysis'].pop('cache_contract')
        (self.old/'orchestration.json').write_text(json.dumps(doc))
        self.assertIsNone(self.reuse())

if __name__=='__main__':unittest.main()
