#!/usr/bin/env python3
"""Production recovery launcher using the unchanged v0.4.0.45 runner.

Only the generator callable is adapted *within this isolated subprocess*. The
complete original recovery algorithm, native toolchain, mapper and runtime are
not rewritten. An explicit RECOMPDEV_TRANSLATOR_MODE=legacy-direct restores the
original unmodified driver without using this wrapper.
"""
from __future__ import annotations
import json
import runpy
import sys
import time
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]
LEGACY=SOURCE/'legacy'/'RecompDev-v0.4.0.45'
sys.path.insert(0,str(SOURCE))
sys.path.insert(0,str(LEGACY))
from production_translation.provider import select_provider, ProviderError

def main():
    args=sys.argv[1:]
    if '--output-dir' not in args or args.index('--output-dir')+1>=len(args):
        raise SystemExit('Missing recovery --output-dir')
    destination=Path(args[args.index('--output-dir')+1]).resolve()
    generate,ident=select_provider()
    import nativecore.continuous_recovery_v0436 as original
    original_generate=original.generate_project
    observations={'schema':'recompdev-production-translation-v1',
                  'status':'ACTIVE','selected_provider':ident,
                  'generator_calls':0,'maximum_translated_instructions':0,
                  'legacy_recovery_engine':'nativecore.continuous_recovery_v0436.run',
                  'fallback_used':False,'gameplay_parity':'NOT_ESTABLISHED'}
    def wrapped(doc,rom,out,overlays=()):
        result=generate(doc,rom,out,overlays)
        observations['generator_calls']+=1
        observations['maximum_translated_instructions']=max(
            observations['maximum_translated_instructions'],int(result.get('translated_instructions',0)))
        return result
    original.generate_project=wrapped
    old_argv=sys.argv
    sys.argv=[str(LEGACY/'tools/Run-Continuous-Recovery-v0445.py'),*args]
    try:
        runpy.run_path(str(LEGACY/'tools/Run-Continuous-Recovery-v0445.py'),run_name='__main__')
    except SystemExit as e:
        observations['original_exit_code']=e.code
        raise
    except Exception as e:
        observations['status']='PROVIDER_OR_LEGACY_RECOVERY_ERROR'
        observations['original_error']=type(e).__name__+': '+str(e)[:300]
        raise
    finally:
        sys.argv=old_argv
        original.generate_project=original_generate
        # Even a recovery budget stop gets a provider witness in upload evidence.
        destination.mkdir(parents=True,exist_ok=True)
        output=destination/'production-translation.json'
        output.write_text(json.dumps(observations,indent=2,sort_keys=True)+'\n',encoding='utf8')

if __name__=='__main__':
    try:main()
    except ProviderError as exc:
        print('PRODUCTION_TRANSLATOR_BLOCKED: '+str(exc),file=sys.stderr)
        raise SystemExit(2)
