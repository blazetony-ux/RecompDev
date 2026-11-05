"""Versioned, independently replaceable discovery provider registry.

The controller owns provider resolution. Inputs do not select plugin names, and
only modules under the installed discovery_integration.providers namespace are
eligible; arbitrary package imports from ROM metadata are prohibited.
"""
from __future__ import annotations
from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Callable, Mapping

CONTRACT = 'recompdev.discovery.provider-registry.v1'
ROLES = ('structure', 'catalogue', 'disc')


@dataclass(frozen=True)
class Provider:
    role: str
    identifier: str
    run: Callable[[Mapping[str, object]], dict]


def load(path: Path | None = None) -> dict[str, Provider]:
    path = Path(path) if path is not None else Path(__file__).with_name('providers.json')
    doc = json.loads(path.read_text(encoding='utf8'))
    if doc.get('schema') != CONTRACT:
        raise ValueError('Discovery provider registry contract mismatch')
    entries = doc.get('providers')
    if not isinstance(entries, list) or len(entries) != len(ROLES):
        raise ValueError('Discovery provider registry requires one provider per role')
    result: dict[str, Provider] = {}
    identifiers = set()
    for descriptor in entries:
        if not isinstance(descriptor, dict):
            raise ValueError('Discovery provider descriptor must be an object')
        role, name, identifier = descriptor.get('role'), descriptor.get('module'), descriptor.get('id')
        if role not in ROLES or role in result or identifier in identifiers:
            raise ValueError('Duplicate or unsupported discovery provider role/id')
        if not isinstance(name, str) or not name.startswith('discovery_integration.providers.'):
            raise ValueError('Provider module outside the discovery integration namespace')
        # Resolve only installed provider modules; externally supplied source bytes,
        # file extensions, and database metadata never choose the import path.
        mod = importlib.import_module(name)
        if getattr(mod, 'ID', None) != identifier or not callable(getattr(mod,'run',None)):
            raise ValueError('Discovery provider identity/API mismatch: '+str(identifier))
        result[role] = Provider(role,identifier,mod.run)
        identifiers.add(identifier)
    if set(result) != set(ROLES):
        raise ValueError('Missing required discovery provider roles')
    return result
