"""Original v0.4.0.45 execution adapters.

Subprocess boundaries deliberately preserve the real production Python services
instead of replacing them with the modular harness's small interpreter.
"""
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / 'legacy' / 'RecompDev-v0.4.0.45'
MANIFEST = ROOT / 'modular' / 'plugins.json'


class PipelineError(RuntimeError):
    pass


def registry():
    entries = json.loads(MANIFEST.read_text(encoding='utf8'))
    if entries.get('schema') != 'recompdev-modular-adapters-v1':
        raise PipelineError('Unknown adapter registry schema')
    result = {}
    for entry in entries['plugins']:
        ident = entry['id']
        if ident in result or ident not in ('legacy.discovery', 'legacy.preparation', 'legacy.recovery', 'legacy.sms-campaign'):
            raise PipelineError('Duplicate or unauthorised plugin registration')
        source = ROOT / entry['source']
        if not source.is_file() or source.resolve() != (LEGACY / {
            'legacy.discovery': 'discovery/engine.py',
            'legacy.preparation': 'nativeprep/engine.py',
            'legacy.recovery': 'tools/Run-Continuous-Recovery-v0445.py',
            'legacy.sms-campaign': 'tools/Run-SMS-Campaign-v0445.py',
        }[ident]).resolve():
            raise PipelineError('Plugin source is not the expected preserved implementation: ' + ident)
        result[ident] = entry
    if len(result) != 4:
        raise PipelineError('Missing required original pipeline adapters')
    return result


def invoke(plugin_id, params, run_dir, timeout=480, extra_env=None):
    """Run preserved service with argv (no shell), bounded log, explicit evidence."""
    available = registry()
    if plugin_id not in available:
        raise PipelineError('Unknown service plugin: '+plugin_id)
    if not (1 <= timeout <= 7200):
        raise PipelineError('Invalid service timeout')
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    # No service log may be created under the frozen release source.
    if run_dir == LEGACY.resolve() or LEGACY.resolve() in run_dir.parents:
        raise PipelineError('Refusing service output within immutable source tree')
    entry = available[plugin_id]
    module = entry['module']
    # The optional production translation provider runs the ENTIRE preserved
    # original recovery runner with its generator callable injected inside an
    # isolated child process. Explicit legacy-direct uses the original script.
    translator_mode = os.environ.get('RECOMPDEV_TRANSLATOR_MODE','preserved-plugin')
    if plugin_id == 'legacy.recovery' and translator_mode not in ('preserved-plugin','legacy-direct'):
        raise PipelineError('Unknown RECOMPDEV_TRANSLATOR_MODE')
    if plugin_id == 'legacy.recovery' and translator_mode == 'preserved-plugin':
        shim = ROOT/'production_translation'/'run_recovery.py'
        if not shim.is_file():
            raise PipelineError('Production translation adapter missing; refuse implicit fallback')
        command = [sys.executable, '-u', str(shim), *map(str,params)]
    elif plugin_id in ('legacy.recovery','legacy.sms-campaign'):
        command = [sys.executable, '-u', str(LEGACY / module), *map(str,params)]
    else:
        command = [sys.executable, '-u', '-m', module, *map(str,params)]
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if extra_env:
        if set(extra_env)-{'RECOMPDEV_CATALOGUE','RECOMPDEV_DATA_DIR'}:
            raise PipelineError('Refusing arbitrary environment override')
        env.update({str(k):str(v) for k,v in extra_env.items()})
    log_file = run_dir / (entry['stage']+'.log')
    record_file = run_dir / (entry['stage']+'.execution.json')
    if log_file.exists() or record_file.exists():
        raise PipelineError('Refusing to overwrite previous service evidence')
    status = 'COMPLETE'
    with log_file.open('wb') as stream:
        proc = None
        try:
            proc = subprocess.Popen(command, cwd=LEGACY, stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.STDOUT, env=env,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0,
                                    start_new_session=os.name!='nt')
            rc=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status='TIMEOUT'; rc=None
            if proc is not None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                   timeout=15,check=False)
                else:
                    try: os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                if proc.poll() is None: proc.kill()
                proc.wait(timeout=10)
        except OSError as exc:
            status = 'LAUNCH_ERROR'; rc = None
            stream.write((f'\nLAUNCH_ERROR: {type(exc).__name__}: {exc}\n').encode('utf8','replace'))
    if status == 'COMPLETE' and rc != 0:
        status = 'BLOCKED_OR_FAILED'
    record = {'plugin': plugin_id, 'original_module': module,
              'original_source': str(ROOT / entry['source']), 'status': status,
              'return_code': rc, 'log': str(log_file),
              'no_gameplay_parity_claim': True, 'preserved_production_implementation': True}
    if plugin_id == 'legacy.recovery':
        record['translation_provider_mode'] = translator_mode
        record['actual_entrypoint'] = command[2] if len(command)>2 else None
    record_file.write_text(json.dumps(record,indent=2)+'\n', encoding='utf8')
    return record
