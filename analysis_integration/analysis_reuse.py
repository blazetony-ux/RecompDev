"""Source/tool/provider-attested initial-analysis reuse across native job cycles.

A cache hit copies only Ghidra's source-attested IR and optional Rizin
hypothesis inputs. It NEVER reuses compiled code, runtime state, bank overlays,
or observed instruction-stop claims. Those still pass independent native gates.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil

from analysis_integration.ghidra_evidence import candidate_rows, read_export, LANG
from analysis_integration.reconciliation import reconcile, sha256_file
from analysis_integration.tool_authorization import authorize_tool
from analysis_integration.providers import ProviderBlocked

SCHEMA = 'recompdev.analysis.cache-contract.v1'
MAINTAINED_FILES = (
    'analysis_integration/analysis_reuse.py',
    'analysis_integration/providers.py',
    'analysis_integration/reconciliation.py',
    'analysis_integration/ghidra_provider.py',
    'analysis_integration/ghidra_evidence.py',
    'analysis_integration/rizin_provider.py',
    'analysis_integration/rizin_compat.py',
    'analysis_integration/tool_authorization.py',
    'analysis_integration/ghidra/ExportFunctionBodies.java',
    'analysis_integration/ghidra/SeedRecompEntry.java',
)
MAX_DOCUMENT = 8 * 1024 * 1024


def _document(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DOCUMENT:
        raise ProviderBlocked('ANALYSIS_CACHE_DOCUMENT_INVALID')
    return json.loads(path.read_text(encoding='utf-8'))


def _artifact(path: Path, parent: Path, digest: str, limit: int = 128 * 1024 * 1024):
    if (path.is_symlink() or not path.is_file() or
        not path.resolve(strict=True).is_relative_to(parent) or not 0 < path.stat().st_size <= limit or
        sha256_file(path) != digest):
        raise ProviderBlocked('ANALYSIS_CACHE_ARTIFACT_HASH_MISMATCH')


def cache_contract(rom: Path, ghidra: Path | None, rizin: Path | None,
                   roots: tuple[Path, ...]) -> dict:
    source = Path(__file__).resolve().parents[1]
    d = hashlib.sha256()
    for rel in MAINTAINED_FILES:
        file = source / rel
        d.update(rel.encode('utf-8') + b'\0')
        d.update(bytes.fromhex(sha256_file(file)))
    tools = {}
    for kind, path in (('ghidra', ghidra), ('rizin', rizin)):
        if path is not None:
            approved = authorize_tool(path, roots, kind)
            tools[kind] = {'path': str(approved), 'sha256': sha256_file(approved)}
    return {'schema': SCHEMA, 'source_sha256': sha256_file(rom),
            'source_bytes': rom.stat().st_size, 'provider_sha256': d.hexdigest(),
            'tools': tools, 'architecture': 'z80', 'platform': 'sms'}


def record_cache_contract(result: dict, output: Path, contract: dict):
    result['cache_contract'] = contract
    result.setdefault('cache_reuse', 'NEW_ANALYSIS')
    (output / 'provider-manifest.json').write_text(
        json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def reuse_initial(previous: Path, rom: Path, output: Path, *, ghidra: Path | None,
                  rizin: Path | None, roots: tuple[Path, ...]):
    """Return (ghidra export, reconciliation, report) or None if cache is stale.

    Mismatched source/tools/providers => fresh analysis. Corrupted or altered
    existing cache artifacts => fail closed, never promote an unverified copy.
    """
    previous = Path(previous).resolve(strict=True)
    rom = Path(rom).resolve(strict=True)
    contract = cache_contract(rom, ghidra, rizin, roots)
    prior = _document(previous / 'orchestration.json')
    if prior.get('schema') != 'recompdev.native.orchestrator.v1' or prior.get('source_sha256') != contract['source_sha256']:
        raise ProviderBlocked('ANALYSIS_CACHE_ROM_IDENTITY_MISMATCH')
    analysis = prior.get('analysis', {})
    if not isinstance(analysis, dict) or analysis.get('cache_contract') != contract:
        return None  # v0.4.9.17 or changed tools/provider requires new analysis.
    if analysis.get('schema') != 'recompdev.analysis.providers.v1':
        raise ProviderBlocked('ANALYSIS_CACHE_PROVIDER_SCHEMA_INVALID')
    if analysis.get('ghidra_execution', {}).get('tool_sha256') != contract['tools'].get('ghidra', {}).get('sha256'):
        raise ProviderBlocked('ANALYSIS_CACHE_GHIDRA_TOOL_MISMATCH')
    if rizin is not None and analysis.get('rizin_execution', {}).get('tool_sha256') != contract['tools'].get('rizin', {}).get('sha256'):
        raise ProviderBlocked('ANALYSIS_CACHE_RIZIN_TOOL_MISMATCH')
    old_dir = previous / 'analysis'
    if old_dir.is_symlink() or not old_dir.is_dir() or old_dir.resolve(strict=True) != old_dir:
        raise ProviderBlocked('ANALYSIS_CACHE_DIRECTORY_INVALID')
    if _document(old_dir / 'provider-manifest.json') != analysis:
        raise ProviderBlocked('ANALYSIS_CACHE_MANIFEST_MISMATCH')
    ghpath = old_dir / 'ghidra-functions.json'
    _artifact(ghpath, previous, analysis.get('ghidra_export_sha256'))
    doc = read_export(ghpath)
    if doc.get('source_sha256') != contract['source_sha256'] or doc.get('language') != LANG['z80']:
        raise ProviderBlocked('ANALYSIS_CACHE_GHIDRA_SOURCE_IDENTITY_MISMATCH')
    functions = candidate_rows(doc, rom, 'z80')
    if (not functions or len(functions) != analysis.get('ghidra_verified_functions') or
        sum(x[2] for x in functions) != analysis.get('ghidra_verified_instructions')):
        raise ProviderBlocked('ANALYSIS_CACHE_VERIFIED_FUNCTIONS_MISMATCH')
    originals = [('ghidra-functions.json', ghpath)]
    reconciliation = None
    if rizin is not None:
        rzpath = old_dir / 'rizin' / 'rizin-aflj.json'
        rz = analysis.get('rizin_execution', {})
        _artifact(rzpath, previous, rz.get('export_sha256'), 32 * 1024 * 1024)
        rec = old_dir / 'reconciled-functions.json'
        _artifact(rec, previous, analysis.get('reconciliation_sha256'), 32 * 1024 * 1024)
        fresh = reconcile(rom, 0, 'z80', ghpath, rzpath)
        # json report writers use Path.write_text(), whose newline='None'
        # on Windows encodes LF as CRLF. The stored artifact has already been
        # verified against its recorded SHA-256 above, so compare its exact
        # canonical text *after universal newline decoding*. Preserve strict
        # JSON structure/ordering/spacing checks without rejecting authentic
        # Windows-created reports on subsequent recovery cycles.
        expected = json.dumps(fresh, sort_keys=True, indent=2) + '\n'
        if rec.read_text(encoding='utf-8') != expected:
            raise ProviderBlocked('ANALYSIS_CACHE_RECONCILIATION_CHANGED')
        originals.extend([('rizin/rizin-aflj.json', rzpath), ('reconciled-functions.json', rec)])
    elif analysis.get('reconciliation_sha256') is not None:
        return None
    output.mkdir(parents=True, exist_ok=False)
    for name, src in originals:
        dst = output / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if sha256_file(dst) != sha256_file(src):
            raise ProviderBlocked('ANALYSIS_CACHE_COPY_VERIFY_FAILED')
    reused = dict(analysis)
    reused['external_tools_executed'] = []
    reused['cache_reuse'] = 'SOURCE_TOOL_PROVIDER_ATTESTED'
    reused['cache_source_orchestration_sha256'] = sha256_file(previous / 'orchestration.json')
    # A previous Ghidra/Rizin execution audit is historical, not an assertion
    # that those tools ran again in the newly cached cycle.
    record_cache_contract(reused, output, contract)
    if rizin is not None:
        reconciliation = output / 'reconciled-functions.json'
    return output / 'ghidra-functions.json', reconciliation, reused
