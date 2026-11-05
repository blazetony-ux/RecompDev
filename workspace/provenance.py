"""Immutable per-run provenance; no ROM or binary blobs embedded in evidence."""
import json
from pathlib import Path


def record_provenance(output, root, report):
    from workspace.manager import read_state, manifest, git_head
    output=Path(output).resolve();root=Path(root).resolve()
    if output==root or root in output.parents:
        raise ValueError('Run evidence must be written outside Git-managed source tree')
    if not output.is_dir():raise ValueError('Run evidence directory does not exist')
    state=read_state(root)
    data={
        'schema':'recompdev-run-provenance-v1',
        'workspace_version':manifest(root)['workspace_release'],
        'git_commit':git_head(root),
        'component_versions':{k:v['version'] for k,v in manifest(root)['components'].items()},
        'runtime_plugins':state['active'],
        'selected_production_workflow':'legacy discovery/preparation/recovery adapter',
        'compiled_harness_plugins_are_not_native_recovery_executors':True,
        'production_cpu_admission_gate':report.get('production_cpu_gate',{'status':'NOT_INVOKED'}),
        'production_translation': report.get('production_translation',{'status':'NOT_RUN'}),
        'status':report.get('status'),
        'rom_sha256':report.get('source_sha256'),
        'rom_contents_included':False,
    }
    target=output/'run-provenance.json'
    if target.exists():raise FileExistsError('Run provenance already exists')
    target.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return data
