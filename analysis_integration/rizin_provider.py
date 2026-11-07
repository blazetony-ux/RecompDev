"""RecompDev-owned, versioned, architecture-neutral Rizin process provider.

The controller requests function *hypotheses* through this provider; analysis
cannot itself authorize translation of source bytes or hardware mapping.
The subprocess and parser are maintained independently of archived scripts.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from analysis_integration.rizin_compat import normalize_rizin_log, RizinCompatibilityError

SCHEMA = 'recompdev.analysis.rizin-provider.v1'
MAX_PROCESS_LOG_BYTES = 2 * 1024 * 1024
# Rizin names and options reflect the existing tested Rizin 0.9.1 CLI, not a
# CPU/console assumption inside the controller. Additional ISAs require tests.
ARCHITECTURES = {
    'z80': ('z80', '8'),
    'm68k': ('m68k', '32'),
    'mips': ('mips', '32'),
}


class RizinProviderError(ValueError):
    """Fail-closed direct analyzer invocation or evidence validation failure."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=8, check=False)
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


def _run_bounded(argv: list[str], timeout: int, logfile: Path) -> dict:
    """Copy combined console output to an exclusive evidence file with hard caps."""
    if not 1 <= timeout <= 3600:
        raise RizinProviderError('RIZIN_TIMEOUT_OUT_OF_BOUNDS')
    over_limit = threading.Event()
    io_error: list[str] = []
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    with tempfile.TemporaryDirectory(prefix='recompdev-rizin-direct-') as cwd:
        with logfile.open('xb') as log:
            try:
                proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        shell=False, creationflags=flags,
                                        start_new_session=os.name != 'nt')
            except OSError as exc:
                raise RizinProviderError('RIZIN_LAUNCH_FAILED') from exc

            def consume() -> None:
                size = 0
                try:
                    while True:
                        block = proc.stdout.read(8192)
                        if not block:
                            break
                        size += len(block)
                        if size > MAX_PROCESS_LOG_BYTES:
                            over_limit.set()
                            break
                        log.write(block)
                except OSError as exc:
                    io_error.append(type(exc).__name__)
                finally:
                    proc.stdout.close()

            reader = threading.Thread(target=consume, daemon=True)
            reader.start()
            started = time.monotonic()
            outcome = 'EXITED'
            while proc.poll() is None:
                if over_limit.is_set():
                    outcome = 'OUTPUT_LIMIT'
                    _terminate_process_tree(proc)
                    break
                if io_error:
                    outcome = 'LOG_IO_ERROR'
                    _terminate_process_tree(proc)
                    break
                if time.monotonic() - started > timeout:
                    outcome = 'TIMEOUT'
                    _terminate_process_tree(proc)
                    break
                time.sleep(0.03)
            reader.join(timeout=5)
            if reader.is_alive():
                _terminate_process_tree(proc)
                outcome = 'LOG_PUMP_UNFINISHED'
            elif over_limit.is_set():
                outcome = 'OUTPUT_LIMIT'
            elif io_error:
                outcome = 'LOG_IO_ERROR'
            elif outcome == 'EXITED' and proc.returncode != 0:
                outcome = 'TOOL_ERROR'
            result = {'status': outcome, 'return_code': proc.returncode}
    result['log_sha256'] = _sha(logfile)
    result['log_bytes'] = logfile.stat().st_size
    return result


def execute_rizin(executable: Path, source: Path, base: int, isa: str,
                  workspace: Path, timeout: int) -> dict:
    """Execute approved Rizin and publish one validated aflj evidence document.

    Caller owns root/explicit-tool approval; this function enforces file and
    source identity, safe CLI parameters, bounded execution and no overwrite.
    Status metadata is saved even if the process returns an error, so failures
    preserve forensic evidence and cannot masquerade as successful analysis.
    """
    executable = Path(executable).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    workspace = Path(workspace)
    if executable.name.lower() not in ('rizin', 'rizin.exe', 'rz', 'rz.exe'):
        raise RizinProviderError('RIZIN_TOOL_NAME_INVALID')
    if isa not in ARCHITECTURES:
        raise RizinProviderError('RIZIN_ARCHITECTURE_UNSUPPORTED')
    if type(base) is not int or not 0 <= base < (1 << 63):
        raise RizinProviderError('RIZIN_BASE_INVALID')
    if not source.is_file() or not 0 < source.stat().st_size <= 32 * 1024 * 1024:
        raise RizinProviderError('RIZIN_SOURCE_INVALID')
    if not workspace.is_dir() or any(workspace.iterdir()):
        raise RizinProviderError('RIZIN_WORKSPACE_NOT_EMPTY')
    if not 1 <= timeout <= 3600:
        raise RizinProviderError('RIZIN_TIMEOUT_OUT_OF_BOUNDS')
    before_source = _sha(source)
    before_tool = _sha(executable)
    arch, bits = ARCHITECTURES[isa]
    # No shell, no -i scripts, no inherited user rizin configuration.
    argv = [str(executable), '-N', '-n', '-q', '-a', arch, '-b', bits,
            '-m', hex(base), '-A', '-c', 'aflj', str(source)]
    raw = workspace / 'rizin-output.log'
    process = _run_bounded(argv, timeout, raw)
    result = {'schema': SCHEMA, 'backend': 'recompdev-owned-rizin-v1',
              'status': process['status'], 'return_code': process['return_code'],
              'source_sha256': before_source, 'tool_sha256': before_tool,
              'tool_version': 'NOT_QUERIED', 'architecture': isa,
              'base': base, 'log_sha256': process['log_sha256'],
              'log_bytes': process['log_bytes'], 'functions_qualified': False,
              'historical_runner_used': False}
    report = workspace / 'rizin-process.json'
    report.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf8')
    if _sha(source) != before_source or _sha(executable) != before_tool:
        raise RizinProviderError('RIZIN_SOURCE_OR_TOOL_CHANGED')
    if result['status'] != 'EXITED':
        return result
    try:
        audit = normalize_rizin_log(raw, workspace / 'rizin-aflj.json',
                                    workspace / 'rizin-provider.json',
                                    expected_log_hash=process['log_sha256'])
    except (RizinCompatibilityError, OSError) as exc:
        raise RizinProviderError('RIZIN_OUTPUT_REJECTED: ' + str(exc)) from exc
    result['normalization'] = audit['normalization']
    result['export_sha256'] = audit['normalized_sha256']
    result['function_count'] = audit['function_count']
    result['warning_count'] = audit['warning_count']
    result['provider_audit_sha256'] = _sha(workspace / 'rizin-provider.json')
    if _sha(source) != before_source or _sha(executable) != before_tool:
        raise RizinProviderError('RIZIN_SOURCE_OR_TOOL_CHANGED')
    return result
