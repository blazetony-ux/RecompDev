"""Source-bound recovery import, missing/forged evidence, and maintained Ghidra parity."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analysis_integration.recovery_history import import_previous, RecoveryHistoryError
from analysis_integration.ghidra_evidence import read_export, candidate_rows
from analysis_integration.reconciliation import reconcile


def sha(b):
    return hashlib.sha256(b).hexdigest()


class RecoveryImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='recompdev-history-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rom = self.root/'a.sms'
        self.data = bytearray(0x10000)
        self.data[0] = 0x76
        self.data[0x9000] = 0x76
        self.rom.write_bytes(self.data)
        self.hash = sha(self.data)
        self.base = self.root/'base.json'
        self.base_doc = {
            'schema': 'recomp-function-pcode-v1', 'analyzer': 'ghidra-raw-pcode',
            'source_sha256': self.hash, 'language':'z80:LE:16:default',
            'target_id': 'mastersystem-'+self.hash[:12],
            'functions': [{'entry':0,'body_min':0,'body_max':0,'instructions':[{
                'address':0,'length':1,'bytes_sha256':sha(self.data[0:1])}]}]}
        self.base.write_text(json.dumps(self.base_doc))
        self.old = self.root/'prior'
        focus = self.old/'round-01-ghidra-recovery'
        focus.mkdir(parents=True)
        self.seed = {'schema':'recompdev.native.app.stop.v1', 'status':'UNTRANSLATED_INITIAL_CODE',
                     'pc':0x9000,'physical_offset':0x9000,'mapper':[0,0,1,2],
                     'sp':0xdffc,'native_steps':500,'rom_bytes':len(self.data),
                     'source_sha256':self.hash}
        self.seed_path = self.old/'round-01-observed-stop.json'
        self.seed_path.write_text(json.dumps(self.seed))
        self.overlay = copy.deepcopy(self.base_doc)
        self.overlay['bank_context'] = {'slot':2,'bank':2,'base':0x8000,'physical_start':0x8000}
        self.overlay['functions'] = [{'entry':0x9000,'body_min':0x9000,'body_max':0x9000,
            'instructions':[{'address':0x9000,'length':1,'bytes_sha256':sha(self.data[0x9000:0x9001])}]}]
        self.overlay_path = focus/'source-verified-bank-functions.json'
        self.overlay_path.write_text(json.dumps(self.overlay))
        self.audit = {'observed_pc': self.seed['pc'], 'observed_physical':self.seed['physical_offset'],
                      'observed_mapper':self.seed['mapper'], 'source_sha256':self.hash}
        (focus/'recovery-audit.json').write_text(json.dumps(self.audit))
        self.orch = {'schema':'recompdev.native.orchestrator.v1', 'source_sha256':self.hash,
                     'rounds':[{'round':1, 'recovery_seed':str(self.seed_path),
                                'ghidra_focused_region':{'backend':'ghidra-headless'}}]}
        (self.old/'orchestration.json').write_text(json.dumps(self.orch))

    def test_valid_hash_attested_import_is_immutable(self):
        before = {p.relative_to(self.old):p.read_bytes() for p in self.old.rglob('*') if p.is_file()}
        seeds,banks,audit = import_previous(self.old,self.root/'imported',self.rom,self.base)
        self.assertEqual((len(seeds),len(banks)),(1,1))
        self.assertEqual(json.loads(seeds[0].read_text())['pc'],0x9000)
        self.assertEqual(audit['verified'],'RECHECKED_SOURCE_MAPPER_INSTRUCTION_HASHES')
        self.assertEqual(sha(banks[0].read_bytes()),sha(self.overlay_path.read_bytes()))
        self.assertEqual(before,{p.relative_to(self.old):p.read_bytes() for p in self.old.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(RecoveryHistoryError,'DESTINATION_INVALID'):
            import_previous(self.old,self.root/'imported',self.rom,self.base)

    def test_rejects_forged_physical_mapper(self):
        self.seed['physical_offset']=0x5000
        self.seed_path.write_text(json.dumps(self.seed))
        with self.assertRaisesRegex(RecoveryHistoryError,'PHYSICAL_MISMATCH'):
            import_previous(self.old,self.root/'imported',self.rom,self.base)

    def test_rejects_wrong_rom(self):
        bad = self.root/'b.sms';bad.write_bytes(bytes(self.data)+b'X')
        with self.assertRaisesRegex(RecoveryHistoryError,'IDENTITY_MISMATCH'):
            import_previous(self.old,self.root/'imported',bad,self.base)

    def test_rejects_forged_pcode_bytes(self):
        self.overlay['functions'][0]['instructions'][0]['bytes_sha256'] = '0'*64
        self.overlay_path.write_text(json.dumps(self.overlay))
        with self.assertRaisesRegex(RecoveryHistoryError,'BYTES_MISMATCH'):
            import_previous(self.old,self.root/'imported',self.rom,self.base)

    def test_rejects_bank_context_mismatch(self):
        self.overlay['bank_context']['bank']=3
        self.overlay_path.write_text(json.dumps(self.overlay))
        with self.assertRaisesRegex(RecoveryHistoryError,'CONTEXT_MISMATCH'):
            import_previous(self.old,self.root/'imported',self.rom,self.base)

    def test_rejects_path_escape(self):
        self.orch['rounds'][0]['recovery_seed']=str(self.root/'other.json')
        (self.old/'orchestration.json').write_text(json.dumps(self.orch))
        (self.root/'other.json').write_text(json.dumps(self.seed))
        with self.assertRaisesRegex(RecoveryHistoryError,'ESCAPES_ROOT'):
            import_previous(self.old,self.root/'imported',self.rom,self.base)

    def test_rejects_repeated_stop(self):
        self.orch['rounds'].append({'round':2,'recovery_seed':str(self.seed_path)})
        (self.old/'orchestration.json').write_text(json.dumps(self.orch))
        with self.assertRaisesRegex(RecoveryHistoryError,'REPEATED'):
            import_previous(self.old,self.root/'imported',self.rom,self.base)

    def _session(self, name, observed_pc, previous):
        root = self.root/name
        imports = root/'imported-history'
        prior_seeds, prior_banks, audit = import_previous(previous, imports, self.rom, self.base)
        self.assertEqual(len(prior_seeds), len(prior_banks))
        focus = root/'round-01-ghidra-recovery'
        focus.mkdir()
        seed = dict(self.seed, pc=observed_pc, physical_offset=observed_pc)
        stop = root/'round-01-observed-stop.json'
        stop.write_text(json.dumps(seed))
        overlay = copy.deepcopy(self.overlay)
        overlay['functions'][0]['entry'] = observed_pc
        overlay['functions'][0]['body_min'] = observed_pc
        overlay['functions'][0]['body_max'] = observed_pc
        overlay['functions'][0]['instructions'][0]['address'] = observed_pc
        overlay['functions'][0]['instructions'][0]['bytes_sha256'] = sha(self.data[observed_pc:observed_pc+1])
        (focus/'source-verified-bank-functions.json').write_text(json.dumps(overlay))
        (focus/'recovery-audit.json').write_text(json.dumps(dict(self.audit, observed_pc=observed_pc, observed_physical=observed_pc)))
        (root/'orchestration.json').write_text(json.dumps({'schema':self.orch['schema'], 'source_sha256':self.hash,
            'rounds':[{'round':1,'recovery_seed':str(stop),'ghidra_focused_region':{'backend':'ghidra-headless'}}]}))
        return root, audit

    def test_three_sessions_retain_every_attested_discovery(self):
        first,audit1 = self._session('session1', 0x9001, self.old)
        self.assertEqual((audit1['inherited_stops'],audit1['new_stops']),(0,1))
        second,audit2 = self._session('session2', 0x9002, first)
        self.assertEqual((audit2['inherited_stops'],audit2['new_stops']),(1,1))
        seeds,banks,audit3 = import_previous(second,self.root/'session3'/'imported-history',self.rom,self.base)
        self.assertEqual([json.loads(p.read_text())['pc'] for p in seeds],[0x9000,0x9001,0x9002])
        self.assertEqual((len(banks),audit3['inherited_stops'],audit3['new_stops']),(3,2,1))
        self.assertEqual(len({sha(p.read_bytes()) for p in banks}),3)

    def test_inherited_seed_mutation_is_rejected(self):
        first,_ = self._session('session1', 0x9001, self.old)
        (first/'imported-history/stop-01.json').write_text('{}')
        with self.assertRaisesRegex(RecoveryHistoryError,'INHERITED_STOP_HASH_MISMATCH'):
            import_previous(first,self.root/'session2'/'imported-history',self.rom,self.base)

    def test_inherited_bank_mutation_is_rejected(self):
        first,_ = self._session('session1', 0x9001, self.old)
        (first/'imported-history/bank-01.json').write_text('{}')
        with self.assertRaisesRegex(RecoveryHistoryError,'INHERITED_BANK_HASH_MISMATCH'):
            import_previous(first,self.root/'session2'/'imported-history',self.rom,self.base)

    def test_inherited_missing_audit_fails_closed(self):
        first,_ = self._session('session1', 0x9001, self.old)
        (first/'imported-history/history-import.json').unlink()
        with self.assertRaisesRegex(RecoveryHistoryError,'MISSING_OR_OVERSIZED'):
            import_previous(first,self.root/'session2'/'imported-history',self.rom,self.base)

    def test_active_analysis_does_not_import_frozen_modules(self):
        active=ROOT/'analysis_integration'
        for path in active.glob('*.py'):
            text=path.read_text()
            self.assertNotIn('from nativeprep',text,path)
            self.assertNotIn('from recovery.',text,path)
            self.assertNotIn('from tooling.',text,path)
            self.assertNotIn('legacy/RecompDev-',text,path)

    def test_export_byte_verification_and_source_identity(self):
        self.assertEqual(candidate_rows(read_export(self.base),self.rom,'z80')[0][2],1)
        doc = copy.deepcopy(self.base_doc)
        doc['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'BYTES_DIFFER'):
            candidate_rows(doc,self.rom,'z80')

    def test_maintained_legacy_reconciliation_parity(self):
        legacy=ROOT/'legacy'/'RecompDev-v0.4.0.45'
        sys.path.insert(0,str(legacy))
        try:
            from tooling.analysis import reconcile as reference
            rz=self.root/'rz.json';rz.write_text(json.dumps([{'offset':0,'size':1}]))
            self.base_doc['functions'][0]['body_min']=0
            self.base_doc['functions'][0]['body_max']=0
            self.base.write_text(json.dumps(self.base_doc))
            self.assertEqual(reconcile(self.rom,0,'z80',self.base,rz), reference(self.rom,0,'z80',self.base,rz))
        finally:
            sys.path.remove(str(legacy))

if __name__=='__main__':unittest.main()
