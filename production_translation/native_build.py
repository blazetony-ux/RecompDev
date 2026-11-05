"""External native project build for the preserved recovery generator.

The original generator, recovery algorithm and source-attested inputs are not
modified. Only CMake's binary directory is moved into the external build root;
two final executables are published into the legacy run's expected output path.
This is necessary because the frozen native session launcher looks there.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from workspace.manager import roots


class NativeBuildError(RuntimeError):
    pass


def _tail(value: str, limit: int = 1400) -> str:
    return value[-limit:].strip()


def build_native_project(project: Path, *, timeout: int = 480,
                         build_root: Path | None = None):
    """Return (pilot_executable, compiler_log), compatible with frozen _build.

    A failed CMake step is fatal, retains its full logs, and does NOT publish a
    stale executable from a previous attempt as the result of that build.
    """
    project = Path(project).resolve(strict=True)
    if not (project / 'CMakeLists.txt').is_file():
        raise NativeBuildError('Native project has no CMakeLists.txt')
    if not 30 <= timeout <= 1800:
        raise ValueError('Native build timeout out of range')
    root = Path(build_root or roots()['build'] / 'native').resolve()
    source = roots()['source'].resolve()
    if root == source or source in root.parents:
        raise NativeBuildError('Native compiler outputs cannot be inside Git source')
    # This short fixed-length path avoids deep MSBuild CMakeScratch/TryCompile
    # trees inside the long, versioned evidence directory on Windows.
    identity = hashlib.sha256(str(project).lower().encode('utf-8')).hexdigest()[:16]
    build = root / identity
    build.mkdir(parents=True, exist_ok=True)
    logs = project / 'compiler-evidence'
    logs.mkdir(parents=True, exist_ok=True)
    conf_log = logs / 'configure.log'
    build_log = logs / 'build.log'
    state_file = logs / 'external-native-build.json'
    manifest = {
        'schema': 'recompdev-external-native-build-v1',
        'source_project': str(project), 'external_build_dir': str(build),
        'native_outputs_under_git': False,
        'status': 'CONFIGURING', 'generator_unchanged': True,
    }
    started = time.monotonic()
    try:
        conf = subprocess.run(['cmake', '-S', str(project), '-B', str(build),
                               '-DCMAKE_BUILD_TYPE=Release'],
                              text=True, capture_output=True, errors='replace',
                              timeout=min(180, timeout), check=False)
        conf_log.write_text(conf.stdout + '\n' + conf.stderr, encoding='utf-8')
        if conf.returncode:
            raise NativeBuildError(f'CMake configure failed (exit {conf.returncode}); '
                                   f'full log: {conf_log}; tail: {_tail(conf.stderr or conf.stdout)}')
        manifest['status'] = 'BUILDING'
        proc = subprocess.run(['cmake', '--build', str(build), '--config', 'Release',
                               '--parallel', '2'], text=True, capture_output=True,
                              errors='replace', timeout=timeout, check=False)
        build_log.write_text(proc.stdout + '\n' + proc.stderr, encoding='utf-8')
        if proc.returncode:
            raise NativeBuildError(f'Native compilation failed (exit {proc.returncode}); '
                                   f'full log: {build_log}; tail: {_tail(proc.stderr or proc.stdout)}')
        def find_executable(name: str):
            choices = [build / 'Release' / (name + '.exe'), build / (name + '.exe'),
                       build / 'Release' / name, build / name]
            return next((p for p in choices if p.is_file()), None)
        pilot = find_executable('RecompDevNativePilot')
        app = find_executable('RecompDevNativeApp')
        if pilot is None or app is None:
            raise NativeBuildError('Expected two native executables after successful CMake build')
        # The untouched launcher checks project/build/Release on Windows and
        # project/build/ on Linux; keep both behaviours without moving CMake.
        # Only the final executables are published there; object/intermediate
        # files, CMake cache, compiler tests and PDBs stay at the external root.
        published = project / 'build' / 'Release' if os.name == 'nt' else project / 'build'
        published.mkdir(parents=True, exist_ok=True)
        for item in (pilot, app):
            dest = published / item.name
            tmp = dest.with_name(dest.name + '.tmp')
            shutil.copy2(item, tmp)
            tmp.replace(dest)
        manifest['status'] = 'BUILT'
        manifest['published_runtime_executables'] = [str(published / p.name) for p in (pilot, app)]
        manifest['external_compilation_seconds'] = round(time.monotonic() - started, 3)
        return pilot, (conf.stdout + '\n' + conf.stderr + '\n' + proc.stdout + '\n' + proc.stderr)[-24000:]
    except subprocess.TimeoutExpired as exc:
        manifest['status'] = 'BUILD_TIMEOUT'
        manifest['error'] = f'{type(exc).__name__}: {exc}'
        raise
    except (OSError, NativeBuildError) as exc:
        manifest['status'] = 'BUILD_FAILED'
        manifest['error'] = str(exc)[:4000]
        raise
    finally:
        state_file.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
