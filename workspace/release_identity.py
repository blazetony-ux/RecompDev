"""Canonical workspace release identity for new source-bound evidence."""
from pathlib import Path
import json
import re


def release(source: Path) -> str:
    path=Path(source)/'workspace/components.json'
    doc=json.loads(path.read_text(encoding='utf8'))
    if doc.get('schema')!='recompdev-components-v1':
        raise ValueError('RELEASE_COMPONENT_REGISTRY_SCHEMA_INVALID')
    version=doc.get('workspace_release')
    if not isinstance(version,str) or re.fullmatch(r'v[0-9]+(?:\.[0-9]+){2,3}',version) is None:
        raise ValueError('RELEASE_VERSION_INVALID')
    return 'workspace/'+version


def evidence_version(source: Path) -> str:
    return release(source).removeprefix('workspace/')
