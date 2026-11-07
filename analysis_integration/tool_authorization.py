"""Maintained executable allowlisting for external analysis providers.

This module belongs to the active analysis layer. It does not import the
historical tool runner and performs no PATH lookups or shell command parsing.
"""
from __future__ import annotations

from pathlib import Path


class ToolAuthorizationError(ValueError):
    """External analyzer not explicitly authorized."""


_ALLOWED_EXECUTABLES = {
    'rizin': frozenset(('rizin', 'rizin.exe', 'rz', 'rz.exe')),
    'ghidra': frozenset(('analyzeheadless', 'analyzeheadless.bat', 'analyzeheadless.sh')),
}


def authorize_tool(path: Path, approved_roots: tuple[Path, ...], kind: str) -> Path:
    """Require an existing, explicitly selected executable beneath allowed roots."""
    if kind not in _ALLOWED_EXECUTABLES:
        raise ToolAuthorizationError('ANALYZER_KIND_UNSUPPORTED')
    if not approved_roots:
        raise ToolAuthorizationError('Tool execution requires --allow-tool-root')
    candidate = Path(path).resolve(strict=True)
    if not candidate.is_file():
        raise ToolAuthorizationError('Tool is not a file: ' + str(candidate))
    roots = [Path(root).resolve(strict=True) for root in approved_roots]
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise ToolAuthorizationError('Executable outside approved tool roots: ' + str(candidate))
    if candidate.name.lower() not in _ALLOWED_EXECUTABLES[kind]:
        raise ToolAuthorizationError('Unexpected ' + kind + ' analyzer executable: ' + candidate.name)
    return candidate
