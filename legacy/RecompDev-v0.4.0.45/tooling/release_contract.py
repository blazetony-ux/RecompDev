"""Single authoritative release version for current-entrypoint tests."""
from pathlib import Path
import re

def version(root):
    value=(Path(root)/'RELEASE_VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'0\.4\.0\.[0-9]+',value):raise ValueError('Invalid release version')
    return value

def assert_entrypoints(root):
    root=Path(root);tag=version(root)
    if 'VERSION '+tag not in (root/'nativepilot/CMakeLists.txt').read_text():raise AssertionError('Native CMake release mismatch')
    if 'v'+tag not in (root/'static/tooling.html').read_text():raise AssertionError('Tooling UI release mismatch')
    if "'release':'"+tag+"'" not in (root/'workbench.py').read_text():raise AssertionError('Workbench API release mismatch')
    return tag
