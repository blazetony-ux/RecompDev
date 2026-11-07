"""Maintained Ghidra headless process provider (Python compatibility, not DLL).

The only permitted scripts are versioned, readable Ghidra exports in this active
component. External Ghidra is authorized by the controller-facing adapter;
process execution is bounded and evidence is generated in fresh directories.
"""
from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from analysis_integration.ghidra_evidence import LANG

SCRIPTS = Path(__file__).resolve().parent / 'ghidra'
MAX_LOG = 16 * 1024 * 1024

class GhidraProviderError(ValueError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1 << 20), b''):
            digest.update(part)
    return digest.hexdigest()


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=8, check=False)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            proc.kill()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=8)


def run_headless(command: list[str], log: Path, output: Path, timeout: int) -> dict:
    """No shell, no PATH-based discovery; preserve bounded raw process log."""
    if not 1 <= timeout <= 7200:
        raise GhidraProviderError('GHIDRA_TIMEOUT_OUT_OF_BOUNDS')
    if not SCRIPTS.joinpath('ExportFunctionBodies.java').is_file() or not SCRIPTS.joinpath('SeedRecompEntry.java').is_file():
        raise GhidraProviderError('GHIDRA_MAINTAINED_SCRIPTS_MISSING')
    tool = Path(command[0])
    before = _sha(tool)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    with log.open('xb') as file:
        try:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=file,
                                    stderr=subprocess.STDOUT, shell=False, creationflags=flags,
                                    start_new_session=os.name != 'nt')
        except OSError as exc:
            raise GhidraProviderError('GHIDRA_LAUNCH_FAILED') from exc
        started = time.monotonic()
        error = None
        while proc.poll() is None:
            if time.monotonic() - started > timeout:
                error = 'GHIDRA_TIMEOUT'
                break
            if log.stat().st_size > MAX_LOG:
                error = 'GHIDRA_LOG_TOO_LARGE'
                break
            time.sleep(0.08)
        if error:
            _terminate(proc)
            raise GhidraProviderError(error)
    if log.stat().st_size > MAX_LOG:
        raise GhidraProviderError('GHIDRA_LOG_TOO_LARGE')
    if _sha(tool) != before:
        raise GhidraProviderError('GHIDRA_TOOL_CHANGED_DURING_EXECUTION')
    if proc.returncode or not output.is_file() or not 0 < output.stat().st_size <= 64 * 1024 * 1024:
        raise GhidraProviderError('GHIDRA_OUTPUT_FAILED')
    return {'schema': 'recompdev.analysis.ghidra-provider.v1', 'backend': 'ghidra-headless-maintained',
            'tool_sha256': before, 'log_sha256': _sha(log), 'export_sha256': _sha(output),
            'return_code': proc.returncode, 'status': 'EXITED'}


def execute_initial(rom: Path, target: str, digest: str, output: Path,
                    executable: Path, timeout: int) -> dict:
    rom = Path(rom).resolve(strict=True)
    executable = Path(executable).resolve(strict=True)
    output = Path(output)
    if _sha(rom) != digest:
        raise GhidraProviderError('GHIDRA_SOURCE_MISMATCH')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='recompdev-ghidra-provider-') as directory:
        folder = Path(directory)
        image = folder / 'rom-initial-window.bin'
        with rom.open('rb') as source:
            image.write_bytes(source.read(0xc000))
        command = [str(executable), str(folder), 'RecompDevZ80Preparation', '-import', str(image),
                   '-loader', 'BinaryLoader', '-loader-baseAddr', '0x0',
                   '-processor', LANG['z80'], '-scriptPath', str(SCRIPTS),
                   '-preScript', 'SeedRecompEntry.java', '0x0',
                   '-postScript', 'ExportFunctionBodies.java', str(output), target, digest, '1000',
                   '-readOnly', '-analysisTimeoutPerFile', '180']
        audit = run_headless(command, output.with_suffix('.ghidra.log'), output, timeout)
    if _sha(rom) != digest:
        raise GhidraProviderError('GHIDRA_SOURCE_CHANGED')
    return audit
