"""Runtime staging verifies immutable hashes but never changes active runtime."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from analysis_integration import runtime_stage

class RuntimeStage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.binary=self.root/'RecompDev.exe';self.binary.write_bytes(b'validated-build')
        self.dll=self.root/'rd_machine_sms.dll';self.dll.write_bytes(b'sms-device')
        self.inventory=self.root/'native-binary-hashes.json'
        self.inventory.write_text(json.dumps([
          {'component':'controller','version':'0.4.24','file':'RecompDev.exe','sha256':hashlib.sha256(self.binary.read_bytes()).hexdigest(),'path':str(self.binary)},
          {'component':'rd_machine_sms','version':'0.1.0','file':self.dll.name,'sha256':hashlib.sha256(self.dll.read_bytes()).hexdigest(),'path':str(self.dll)}
        ]))
        self.target=self.root/'staged'/'v29'
        self.active=self.root/'active'/'RecompDev.exe';self.active.parent.mkdir()
        self.active.write_bytes(b'old-working-build')

    def test_stage_verify_and_immutable_no_active_changes(self):
        self.assertEqual(runtime_stage.stage(self.inventory,self.target,'workspace/v0.4.9.29')['status'],'STAGED_NOT_ACTIVATED')
        self.assertEqual(runtime_stage.verify(self.target,self.inventory)['components'],2)
        self.assertEqual(self.active.read_bytes(),b'old-working-build')
        with self.assertRaisesRegex(runtime_stage.StageError,'ALREADY_EXISTS'):
            runtime_stage.stage(self.inventory,self.target,'workspace/v0.4.9.29')

    def test_staged_binary_tamper_blocked(self):
        runtime_stage.stage(self.inventory,self.target,'workspace/v0.4.9.29')
        (self.target/'rd_machine_sms.dll').write_bytes(b'modified')
        with self.assertRaisesRegex(runtime_stage.StageError,'BINARY_CHANGED'):
            runtime_stage.verify(self.target,self.inventory)

    def test_manifest_changed_with_matching_binary_still_fails_independent_inventory(self):
        runtime_stage.stage(self.inventory,self.target,'workspace/v0.4.9.29')
        path=self.target/'rd_machine_sms.dll';path.write_bytes(b'resigned locally')
        manifest=self.target/'image-manifest.json'; doc=json.loads(manifest.read_text())
        record=next(x for x in doc['components'] if x['component']=='rd_machine_sms')
        record['sha256']=hashlib.sha256(path.read_bytes()).hexdigest();record['size']=path.stat().st_size
        manifest.write_text(json.dumps(doc))
        with self.assertRaisesRegex(runtime_stage.StageError,'INVENTORY_MISMATCH'):
            runtime_stage.verify(self.target,self.inventory)

    def test_wrong_build_inventory_hash_rejected(self):
        self.binary.write_bytes(b'wrong')
        with self.assertRaisesRegex(runtime_stage.StageError,'HASH_MISMATCH'):
            runtime_stage.stage(self.inventory,self.target,'workspace/v0.4.9.29')
        self.assertFalse(self.target.exists())
        self.assertEqual(self.active.read_bytes(),b'old-working-build')

if __name__=='__main__':unittest.main()
