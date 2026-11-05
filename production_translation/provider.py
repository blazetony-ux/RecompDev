"""Hash-locked production adapter loader; never modify protected v0.4.0.45.

Each run has an explicit provenance witness. A missing/mismatched provider
blocks, instead of silently switching to an unrelated translator.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'legacy' / 'RecompDev-v0.4.0.45'
REGISTRY = ROOT / 'production_translation' / 'providers.json'

class ProviderError(RuntimeError):
    pass

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):
            h.update(b)
    return h.hexdigest()

def select_provider(root=ROOT):
    root=Path(root).resolve()
    config=json.loads((root/'production_translation/providers.json').read_text(encoding='utf8'))
    if config.get('schema') != 'recompdev-production-translation-providers-v1':
        raise ProviderError('TRANSLATOR_REGISTRY_INVALID')
    selected=config.get('active')
    record=config.get('providers',{}).get(selected)
    if not record or not isinstance(selected,str) or not selected or len(selected)>80:
        raise ProviderError('UNREGISTERED_PRODUCTION_TRANSLATOR')
    rel=record['source']
    path=(root/rel).resolve()
    if not path.is_relative_to(root/'production_translation/providers') or path.suffix!='.py' or not path.is_file() or path.is_symlink():
        raise ProviderError('TRANSLATOR_SOURCE_MISSING')
    if sha256(path)!=record['source_sha256']:
        raise ProviderError('TRANSLATOR_SOURCE_SHA256_MISMATCH')
    legacy=(root/record['legacy_generator']).resolve()
    if not legacy.is_relative_to(root/'legacy') or not legacy.is_file():
        raise ProviderError('PRESERVED_GENERATOR_MISSING')
    if sha256(legacy)!=record['legacy_generator_sha256']:
        raise ProviderError('PRESERVED_GENERATOR_SHA256_MISMATCH')
    spec=importlib.util.spec_from_file_location('recomp_selected_production_translator',path)
    if spec is None or spec.loader is None:
        raise ProviderError('TRANSLATOR_MODULE_UNLOADABLE')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module,'generate_project',None)):
        raise ProviderError('TRANSLATOR_ENTRYPOINT_MISSING')
    return module.generate_project, {
        'component': 'production_translation',
        'provider':selected, 'version':record['version'],
        'source':rel, 'sha256':record['source_sha256'],
        'preserved_generator':record['legacy_generator'],
        'preserved_generator_sha256':record['legacy_generator_sha256'],
        'semantic_native_codegen_engine':'original nativepilot.generator',
        'runtime_plugin_dll_executed':False,
        'independent_gameplay_parity':'NOT_ESTABLISHED'
    }
