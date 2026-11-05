"""CPU-agnostic controller integration for preserved discovery v1 providers.

No direct access to a game-specific decoder, no native generation or CPU fallback.
Report records fresh versus cached work; nonzero outstanding task count is not
reported as completed coverage. The source catalogue is never written.
"""
from __future__ import annotations
import json
from pathlib import Path
from . import CONTRACT, VERSION
from .registry import load


def audit(source, working_catalogue, discovery_report, output, *, legacy_root,
          export_candidates=False):
    source = Path(source).resolve(strict=True)
    db = Path(working_catalogue).resolve(strict=True)
    original = Path(legacy_root).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Discovery audit evidence already exists: '+str(output))
    project = Path(__file__).resolve().parents[1]
    if (output == source or output == db or output == original or original in output.parents
            or output == project or project in output.parents):
        raise ValueError('Audit output overlaps input, working catalogue or source history')
    # Versioned role registry is resolved by the controller, never ROM names.
    providers = load()
    context = {'source':source, 'catalogue':db, 'legacy_root':original}
    observed = providers['structure'].run(context)
    cache = providers['catalogue'].run(context)
    report_path = Path(discovery_report).resolve(strict=True)
    legacy = json.loads(report_path.read_text(encoding='utf-8'))
    run = legacy.get('run', {})
    tasks = run.get('tasks_executed')
    if not isinstance(tasks,int) or tasks < 0:
        raise ValueError('Preserved discovery report has no valid task count')
    result = {'schema': CONTRACT, 'component_version': VERSION, 'source_size':source.stat().st_size,
              'provider_contract': 'recompdev.discovery.provider-registry.v1',
              'providers': {role: p.identifier for role,p in providers.items()},
              'structural': observed, 'cache': cache, 'disc': None,
              'legacy_run_tasks_executed': tasks,
              'legacy_scheduler_source_scoped': False,
              'fresh_work_for_this_input_verified': False,
              'native_translation_qualified': False, 'hardware_parity_qualified': False}
    # No evidence directory is created before metadata validation succeeds.
    output.mkdir(parents=True, exist_ok=False)
    if observed['format'] == 'iso9660':
        context['export_dir'] = output/'extracted-candidates' if export_candidates else None
        result['disc'] = providers['disc'].run(context)
    if tasks == 0:
        result['discovery_progress'] = 'NO_NEW_LEGACY_TASKS_EXECUTED'
    else:
        # Existing scheduler selects across the entire working catalogue,
        # not just the explicitly requested source. Don't misattribute tasks.
        result['discovery_progress'] = 'LEGACY_TASKS_EXECUTED_SOURCE_ATTRIBUTION_UNVERIFIED'
    if cache['matching_source_record']:
        result['outstanding_tasks'] = cache.get('outstanding_total',0)
        result['coverage_status'] = ('CACHED_UNRESOLVED' if result['outstanding_tasks'] else
                                     'CACHED_TASKS_RESOLVED_NOT_PARITY')
    else:
        result['outstanding_tasks'] = None
        result['coverage_status'] = 'NO_AUTHENTICATED_CACHED_COVERAGE'
    out = output/'universal-discovery.json'
    out.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n',encoding='utf-8')
    return {'status':'AUDITED', 'schema': CONTRACT, 'report':str(out),
            'format': observed['format'], 'mapping_status':observed.get('mapping_status'),
            'discovery_progress':result['discovery_progress'], 'coverage_status':result['coverage_status'],
            'outstanding_tasks':result['outstanding_tasks'],
            'disc_candidates':len(result['disc']['candidates']) if result['disc'] else None}
