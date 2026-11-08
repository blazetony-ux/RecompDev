#!/usr/bin/env python3
"""Real RecompDev.exe CLI dispatch smoke in an isolated user-state directory.

Only fake analyzer *path fixtures* are used. No external analyzer is executed and
no game ROM is compiled by this test.
"""
import os,subprocess,sys,tempfile,json,zipfile
from pathlib import Path

exe=Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='recompdev-controller-cli-') as tmp:
    root=Path(tmp);home=root/'state';tools=root/'tools';tools.mkdir()
    gh=tools/'analyzeHeadless.bat';rz=tools/'rizin.exe'
    gh.write_bytes(b'fixture');rz.write_bytes(b'fixture')
    env={**os.environ,'RECOMPDEV_HOME':str(home)}
    def call(*args):return subprocess.run([str(exe),*args],capture_output=True,text=True,env=env,timeout=20)
    p=call('--version');assert p.returncode==0 and '0.4.9.25' in p.stdout,(p.stdout,p.stderr)
    p=call('status');assert p.returncode==2 and 'JOB_FILE_MISSING_OR_TOO_LARGE' in p.stderr,(p.stdout,p.stderr)
    p=call('configure','--ghidra',str(gh),'--rizin',str(rz),'--workspace',str(root/'workspace'),'--logging','info')
    assert p.returncode==0 and 'RECOMPDEV_CONFIGURATION=VERIFIED' in p.stdout,(p.stdout,p.stderr)
    assert (home/'config.json').exists()
    assert (root/'workspace').is_dir() is False  # never create job workspace just by configuring
    p=call('diagnostics','export','--job','../../evil')
    assert p.returncode==2 and 'INVALID_JOB_ID' in p.stderr,(p.stdout,p.stderr)
    fake_job='job-cli-fixture-01'
    fake_dir=root/'workspace'/'v0.4.9.25'/'jobs'/fake_job
    fake_dir.mkdir(parents=True)
    (fake_dir/'job.json').write_text(json.dumps({'schema':'recompdev.controller.job.v1','id':fake_job,
      'status':'RECOVERY_LIMIT_REACHED','rom':'C:\\Users\\owner\\private.sms',
      'rom_sha256':'a'*64,'target_frames':1800,'attempts':[], 'ghidra':'', 'rizin':'', 'plugin_dir':'', 'allow_tool_roots':[], 'max_cycles':2,'rounds_per_cycle':1,'timeout':600,'step_budget':1000,'stagnant':0}))
    p=call('diagnostics','export','--job',fake_job)
    assert p.returncode==0 and 'RECOMPDEV_DIAGNOSTICS_ZIP=' in p.stdout,(p.stdout,p.stderr)
    archive=root/'workspace'/'v0.4.9.25'/'diagnostics'/(fake_job+'-cycles-00-diagnostics.zip')
    assert archive.is_file(),(p.stdout,p.stderr)
    with zipfile.ZipFile(archive) as z:
        assert 'PRIVATE-ROM-DATA' not in '\n'.join(z.namelist())
        assert '<local-path-redacted>' in z.read('job.json').decode()
    # Existing v0.4.9.17 jobs remain read-only and their ZIPs go into v18.
    legacy_id='job-old-workspace-01'; old=root/'workspace'/'v0.4.9.17'/'jobs'/legacy_id
    old.mkdir(parents=True)
    old_doc=dict(json.loads((fake_dir/'job.json').read_text()), id=legacy_id)
    (old/'job.json').write_text(json.dumps(old_doc))
    p=call('diagnostics','export','--job',legacy_id)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert (root/'workspace'/'v0.4.9.25'/'diagnostics'/(legacy_id+'-cycles-00-diagnostics.zip')).is_file()
    assert not (root/'workspace'/'v0.4.9.17'/'diagnostics').exists()
    # Pre-v0.4.9.17 AppData jobs are also routed to current evidence root.
    app_id='job-legacy-appdata-01'; app=home/'jobs'/app_id;app.mkdir(parents=True)
    (app/'job.json').write_text(json.dumps(dict(old_doc,id=app_id)))
    p=call('diagnostics','export','--job',app_id)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert (root/'workspace'/'v0.4.9.25'/'diagnostics'/(app_id+'-cycles-00-diagnostics.zip')).is_file()
    assert not (home/'diagnostics').exists()
    # The owner's existing v0.4.9.17 --workspace setting must be upgraded
    # transparently to the v0.4.9.25 version folder, without moving jobs.
    p=call('configure','--workspace',str(root/'workspace'/'v0.4.9.17'))
    assert p.returncode==0 and ('RECOMPDEV_EVIDENCE_ROOT='+str(root/'workspace')) in p.stdout,(p.stdout,p.stderr)
    assert ('RECOMPDEV_WORKSPACE='+str(root/'workspace'/'v0.4.9.25')) in p.stdout,(p.stdout,p.stderr)
    p=call('diagnostics','export','--job',legacy_id)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert (root/'workspace'/'v0.4.9.25'/'diagnostics'/(legacy_id+'-cycles-00-diagnostics.zip')).is_file()
    p=call('configure','--evidence-root',str(root/'explicit-root'))
    assert p.returncode==0 and ('RECOMPDEV_EVIDENCE_ROOT='+str(root/'explicit-root')) in p.stdout,(p.stdout,p.stderr)
    assert ('RECOMPDEV_WORKSPACE='+str(root/'explicit-root'/'v0.4.9.25')) in p.stdout
    p=call('run','--rom',str(root/'missing.sms'),'--logging','error')
    assert p.returncode==2 and p.stderr.startswith('RECOMPDEV_JOB_ERROR='),(p.stdout,p.stderr)
    assert [x.parent.name for x in (home/'jobs').glob('*/job.json')]==[app_id],(p.stdout,p.stderr)
    p=call('run','--rom',str(root/'missing.sms'),'--logging','trace')
    assert p.returncode==2 and 'INVALID_LOGGING_LEVEL' in p.stderr,(p.stdout,p.stderr)
    p=call('resume','--job','../../evil');assert p.returncode==2 and 'INVALID_JOB_ID' in p.stderr,(p.stdout,p.stderr)
print('PASS: real RecompDev.exe CLI dispatch, configure and fail-closed arguments')
