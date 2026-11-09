"""CPU-neutral replay inheritance/identity contract for automatic recovery."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from analysis_integration.cli import inherit_attested_input_replay,RecoveryBlocked

class Reuse(unittest.TestCase):
    def test_input_timeline_is_reused_identically_and_tamper_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);old=base/'session';new=base/'next'
            old.mkdir();new.mkdir()
            rom_hash='a'*64
            data=b'RECOMP_INPUT_CYCLES_V1\n0,0,0\n500,0,16\n600,0,0\n'
            (old/'preview-input.csv').write_bytes(data)
            input_hash=hashlib.sha256(data).hexdigest()
            report={'schema':'recompdev.native.orchestrator.v1','source_sha256':rom_hash,
                'preview_handoff':{'input_mode':'GUEST_CYCLE_REPLAY_ATTESTED',
                                   'input_sha256':input_hash}}
            (old/'orchestration.json').write_text(json.dumps(report))
            copied,handoff=inherit_attested_input_replay(old,new,rom_hash)
            self.assertEqual(copied.read_bytes(),data)
            self.assertEqual(handoff['input_sha256'],input_hash)
            with self.assertRaises(FileExistsError):inherit_attested_input_replay(old,new,rom_hash)
            (old/'preview-input.csv').write_bytes(data+b'700,0,16\n')
            with self.assertRaisesRegex(RecoveryBlocked,'IDENTITY_MISMATCH'):
                inherit_attested_input_replay(old,base/'new2',rom_hash)
    def test_rejects_invalid_stored_input_and_cross_rom_history(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);old=base/'previous';old.mkdir()
            bad=b'RECOMP_INPUT_CYCLES_V1\n500,0,16\n400,0,0\n'
            (old/'preview-input.csv').write_bytes(bad)
            old.joinpath('orchestration.json').write_text(json.dumps({
                'schema':'recompdev.native.orchestrator.v1','source_sha256':'a'*64,
                'preview_handoff':{'input_mode':'GUEST_CYCLE_REPLAY_ATTESTED',
                'input_sha256':hashlib.sha256(bad).hexdigest()}}))
            with self.assertRaises(ValueError):inherit_attested_input_replay(old,base/'new','a'*64)
            with self.assertRaisesRegex(RecoveryBlocked,'IDENTITY_MISMATCH'):
                inherit_attested_input_replay(old,base/'other','b'*64)
    def test_neutral_previous_history_has_no_replay(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);old=base/'previous';old.mkdir()
            old.joinpath('orchestration.json').write_text(json.dumps({
                'schema':'recompdev.native.orchestrator.v1','source_sha256':'a'*64}))
            self.assertEqual(inherit_attested_input_replay(old,base/'new','a'*64),(None,None))

if __name__=='__main__':unittest.main()
