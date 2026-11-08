"""Real provider replay against a materialised, evidence-independent capsule.

Authenticates synthetic source and bank overlays via the maintained Python
provider after the original history directory is removed. Does not claim live
gameplay, native binary reuse, or extra CPU support.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analysis_integration.analysis_reuse import cache_contract, record_cache_contract, reuse_initial
from analysis_integration.recovery_history import import_previous

PROGRAM = None

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

class PortableReplay(unittest.TestCase):
    def test_analysis_and_bank_overlay_survive_original_deletion(self):
        with tempfile.TemporaryDirectory(prefix='recompdev-capsule-provider-') as location:
            root = Path(location)
            rom = root/'game.sms'
            data = bytearray(0x10000)
            data[0] = 0x76
            data[0x9000] = 0x76
            rom.write_bytes(data)
            digest = sha(data)
            tools = root/'tools'
            tools.mkdir()
            gh = tools/'analyzeHeadless.bat'
            gh.write_bytes(b'approved fixture ghidra')
            prior = root/'historical'/'jobs'/'old-job'/'sessions'/'cycle-01'
            analysis_dir = prior/'analysis'
            analysis_dir.mkdir(parents=True)
            initial = {
                'schema':'recomp-function-pcode-v1', 'analyzer':'ghidra-raw-pcode',
                'source_sha256':digest, 'language':'z80:LE:16:default',
                'target_id':'mastersystem-'+digest[:12],
                'functions':[{'entry':0,'body_min':0,'body_max':0,
                    'instructions':[{'address':0,'length':1,'bytes_sha256':sha(data[:1])}]}]
            }
            export = analysis_dir/'ghidra-functions.json'
            export.write_text(json.dumps(initial))
            attestation = cache_contract(rom,gh,None,(tools,))
            analysis = {
                'schema':'recompdev.analysis.providers.v1',
                'source_sha256':digest, 'architecture':'z80', 'platform':'sms',
                'ghidra_export_sha256':sha(export.read_bytes()),
                'ghidra_verified_functions':1,'ghidra_verified_instructions':1,
                'ghidra_execution':{'tool_sha256':sha(gh.read_bytes())},
                'reconciliation_sha256':None,
                'external_tools_executed':['ghidra'],
            }
            record_cache_contract(analysis,analysis_dir,attestation)
            seed = {'schema':'recompdev.native.app.stop.v1', 'source_sha256':digest,
                'rom_bytes':len(data), 'status':'UNTRANSLATED_INITIAL_CODE',
                'pc':0x9000, 'physical_offset':0x9000,'mapper':[0,0,1,2],
                'sp':0xdffc,'native_steps':500}
            (prior/'round-01-observed-stop.json').write_text(json.dumps(seed))
            overlay = dict(initial)
            overlay['bank_context'] = {'slot':2,'bank':2,'base':0x8000,'physical_start':0x8000}
            overlay['functions'] = [{'entry':0x9000,'body_min':0x9000,'body_max':0x9000,
                'instructions':[{'address':0x9000,'length':1,'bytes_sha256':sha(data[0x9000:0x9001])}]}]
            focused = prior/'round-01-ghidra-recovery'
            focused.mkdir()
            (focused/'source-verified-bank-functions.json').write_text(json.dumps(overlay))
            (focused/'recovery-audit.json').write_text(json.dumps({
                'observed_pc':0x9000, 'observed_physical':0x9000,
                'observed_mapper':[0,0,1,2],'source_sha256':digest}))
            (prior/'orchestration.json').write_text(json.dumps({
                'schema':'recompdev.native.orchestrator.v1','status':'MAX_RECOVERY_ROUNDS_REACHED',
                'source_sha256':digest,'analysis':analysis,
                'rounds':[{'round':1,'frames':55,'emitted':123,
                    'recovery_seed':str(prior/'round-01-observed-stop.json'),
                    'ghidra_focused_region':{'backend':'ghidra-headless'}}]}))
            portable = root/'portable-cache'
            result = subprocess.run([str(PROGRAM),'--promote',str(prior),digest,str(portable)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            old_session = Path(result.stdout.strip())
            self.assertTrue((old_session/'analysis/ghidra-functions.json').is_file())
            shutil.rmtree(root/'historical')
            # Relocate the entire store and all objects after deleting source.
            moved = root/'moved-cache'
            portable.rename(moved)
            session = moved / old_session.relative_to(portable)
            self.assertTrue(session.is_dir())
            output = root/'reused-analysis'
            ghout, reconciliation, audit = reuse_initial(session,rom,output,ghidra=gh,rizin=None,roots=(tools,))
            self.assertIsNone(reconciliation)
            self.assertEqual(audit['cache_reuse'],'SOURCE_TOOL_PROVIDER_ATTESTED')
            self.assertEqual(ghout.read_bytes(),export.read_bytes() if export.exists() else json.dumps(initial).encode())
            seeds,banks,history = import_previous(session,root/'reused-history',rom,ghout)
            self.assertEqual((len(seeds),len(banks)),(1,1))
            self.assertEqual(history['verified'],'RECHECKED_SOURCE_MAPPER_INSTRUCTION_HASHES')
            self.assertEqual(json.loads(seeds[0].read_text())['pc'],0x9000)
            self.assertFalse((root/'historical').exists())

if __name__=='__main__':
    PROGRAM = Path(sys.argv[1]).resolve()
    del sys.argv[1]
    unittest.main()
