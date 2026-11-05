"""Provider contract, exact generator output, hash pinning and real native recovery."""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.append(str(ROOT/'legacy/RecompDev-v0.4.0.45'))
from production_translation.provider import select_provider, ProviderError, sha256
from nativepilot.generator import generate_project
from modular.plugins import legacy

ROM=ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT=ROOT/'harness/examples/recomp-pcode/function-export.json'

class TestProductionTranslation(unittest.TestCase):
    def test_provider_exact_generated_translation_parity(self):
        # Same authenticated initial 6 instruction fixture; output must be byte-identical.
        doc=json.loads(EXPORT.read_text(encoding='utf8'))
        generate,ident=select_provider(ROOT)
        with tempfile.TemporaryDirectory(prefix='recomp-pcode-parity-') as t:
            base=Path(t)/'original';plug=Path(t)/'plugin'
            first=generate_project(doc,ROM,base)
            second=generate(doc,ROM,plug)
            self.assertEqual(first,second)
            old={x.relative_to(base):sha256(x) for x in base.rglob('*') if x.is_file()}
            new={x.relative_to(plug):sha256(x) for x in plug.rglob('*') if x.is_file()}
            self.assertEqual(old,new)
            self.assertGreater(first['translated_instructions'],0)
            self.assertEqual(ident['preserved_generator_sha256'],sha256(ROOT/'legacy/RecompDev-v0.4.0.45/nativepilot/generator.py'))

    def test_hash_mismatch_refuses_unverified_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for rel in ('production_translation/providers.json',
                        'production_translation/providers/preserved_pcode.py',
                        'legacy/RecompDev-v0.4.0.45/nativepilot/generator.py'):
                dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
            (root/'production_translation/providers/preserved_pcode.py').write_text('changed',encoding='utf8')
            with self.assertRaisesRegex(ProviderError,'TRANSLATOR_SOURCE_SHA256_MISMATCH'):select_provider(root)

    def test_explicit_registry_switch_changes_selected_callable(self):
        # Test-only adapter changes generated code; original historical generator is unchanged.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for rel in ('production_translation/providers.json',
                        'production_translation/providers/preserved_pcode.py',
                        'legacy/RecompDev-v0.4.0.45/nativepilot/generator.py'):
                dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
            alternative=root/'production_translation/providers/probe.py'
            alternative.write_text('def generate_project(doc,rom,out,overlays=()):\n'
               ' from nativepilot.generator import generate_project\n'
               ' from pathlib import Path\n'
               ' result=generate_project(doc,rom,out,overlays)\n'
               ' path=Path(out)/"translated.cpp"\n'
               ' path.write_bytes(path.read_bytes()+b"\\n// TEST PROVIDER MARKER\\n")\n'
               ' return result\n',encoding='utf8')
            registry=root/'production_translation/providers.json'
            conf=json.loads(registry.read_text(encoding='utf8'))
            conf['active']='probe'
            conf['providers']['probe']={**conf['providers']['preserved-pcode'],
                  'source':'production_translation/providers/probe.py',
                  'source_sha256':sha256(alternative),'version':'test-only'}
            registry.write_text(json.dumps(conf),encoding='utf8')
            alternate,identity=select_provider(root)
            self.assertEqual(identity['provider'],'probe')
            with tempfile.TemporaryDirectory() as stage:
                doc=json.loads(EXPORT.read_text(encoding='utf8'))
                alternate(doc,ROM,stage)
                self.assertIn(b'TEST PROVIDER MARKER',(Path(stage)/'translated.cpp').read_bytes())

    def test_recovery_invoke_uses_new_runner_by_default_and_original_as_explicit_fallback(self):
        # Observe actual subprocess source routing without C++ recompilation.
        with tempfile.TemporaryDirectory(prefix='recomp-translation-run-') as temp:
            base=Path(temp)
            args=['--rom',ROM,'--export',EXPORT,'--frames','1','--steps','40',
                  '--max-recoveries','0','--compile-timeout','120','--no-history-import',
                  '--coverage-cache',base/'cache.sqlite']
            with patch.dict(__import__('os').environ, {'RECOMPDEV_TRANSLATOR_MODE':'preserved-plugin'}):
                outcome=legacy.invoke('legacy.recovery',[*args,'--output-dir',base/'plugin'],base/'log-plugin',timeout=150)
            self.assertEqual(outcome['translation_provider_mode'],'preserved-plugin')
            self.assertEqual(outcome['status'],'BLOCKED_OR_FAILED' if outcome['return_code']==2 else 'COMPLETE',outcome)
            witness=base/'plugin/production-translation.json'
            self.assertTrue(witness.is_file(),outcome)
            reported=json.loads(witness.read_text(encoding='utf8'))
            self.assertEqual(reported['selected_provider']['provider'],'preserved-pcode')
            self.assertGreater(reported['generator_calls'],0)
            self.assertTrue((base/'plugin/continuous-recovery-report.json').is_file())
            with patch.dict(__import__('os').environ, {'RECOMPDEV_TRANSLATOR_MODE':'legacy-direct'}):
                direct=legacy.invoke('legacy.recovery',[*args,'--output-dir',base/'direct'],base/'log-direct',timeout=150)
            self.assertEqual(direct['translation_provider_mode'],'legacy-direct')
            self.assertFalse((base/'direct/production-translation.json').exists())
            orig=json.loads((base/'direct/continuous-recovery-report.json').read_text(encoding='utf8'))
            via=json.loads((base/'plugin/continuous-recovery-report.json').read_text(encoding='utf8'))
            # Matching bounded run and translated-instruction counts, NOT gameplay parity.
            self.assertEqual(via['status'],orig['status'])
            self.assertEqual(via['attempts'][0]['translated_instructions'],orig['attempts'][0]['translated_instructions'])

if __name__=='__main__':unittest.main()
