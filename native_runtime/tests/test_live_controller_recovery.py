"""v0.4.9.27: full controller->compiler->DLL->same-process guest recovery.

Only the explicitly gated synthetic test exporter is used; the production path
still requires the approved Ghidra/Rizin providers. No ROM-specific exceptions.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

controller = Path(sys.argv[1]).resolve(strict=True)
source = Path(sys.argv[2]).resolve(strict=True)
script = source / 'analysis_integration' / 'live_session.py'
assert script.is_file()
# Path-layout regression: MSVC's generated VCTargetsPath.lastbuildstate may
# exceed MAX_PATH if CMake is nested under the long versioned test evidence.
# Verify our separate, owner-writable compiler scratch root without requiring
# any Windows registry adjustment or compiling a second project.
sys.path.insert(0,str(source))
from analysis_integration.live_session import windows_native_build_workspace
with tempfile.TemporaryDirectory(prefix='rd27-compact-path-test-') as test_parent:
    previous=os.environ.get('LOCALAPPDATA')
    try:
        os.environ['LOCALAPPDATA']=test_parent
        scratch=windows_native_build_workspace()
        try:
            assert Path(scratch.name).is_relative_to(Path(test_parent)/'RecompDev'/'nb')
            estimated=Path(scratch.name)/'recovery-0001'/'build'/'CMakeFiles'/'4.4.4'/\
                'VCTargetsPath'/'x64'/'Debug'/'VCTargetsPath.tlog'/'VCTargetsPath.lastbuildstate'
            assert len(str(estimated))<240,estimated
        finally:
            scratch.cleanup()
        assert not Path(scratch.name).exists(),scratch.name
        os.environ['LOCALAPPDATA']=str(Path(test_parent)/('deep-'*35))
        try:
            windows_native_build_workspace()
        except Exception as exc:
            assert 'WINDOWS_NATIVE_BUILD_ROOT_TOO_LONG' in str(exc),repr(exc)
        else:
            raise AssertionError('Expected long compilation path to fail before CMake')
    finally:
        if previous is None:os.environ.pop('LOCALAPPDATA',None)
        else:os.environ['LOCALAPPDATA']=previous

with tempfile.TemporaryDirectory(prefix='rd-v27-controller-autonomous-') as directory:
    root = Path(directory)
    home = root / 'home'
    home.mkdir()
    evidence = root / 'RecompDev-Evidence'
    # Generic Z80 control flow exercises two independent demand compilations:
    # 0x0009 -> 0x2000 -> 0x2100 (the final block loops, allowing frames).
    rom_data = bytearray(0x8000)
    rom_data[0:11] = bytes.fromhex('00 31 f0 df 21 00 20 e5 e1 e9 76')
    rom_data[0x38] = rom_data[0x66] = 0x76
    rom_data[0x2000:0x2006] = bytes.fromhex('21 00 21 e9 76 76')
    rom_data[0x2100:0x2102] = bytes.fromhex('18 fe')
    rom_data[0x7ff0:0x7ff8] = b'TMR SEGA'
    rom = root / 'novel.sms'
    rom.write_bytes(rom_data)
    digest = hashlib.sha256(rom_data).hexdigest()
    export = root / 'export.json'
    export.write_text(json.dumps({
        'schema': 'recomp-function-pcode-v1',
        'target_id': 'synthetic-controller-autonomous',
        'source_sha256': digest,
        'language': 'z80:LE:16:default',
        'analyzer': 'ghidra-raw-pcode',
        'bank_context': None,
        'functions': [{
            'entry': 0, 'body_min': 0, 'body_max': 0,
            'instructions': [{
                'address': 0, 'length': 1,
                'bytes_sha256': hashlib.sha256(b'\x00').hexdigest(),
                'mnemonic': 'NOP', 'pcode': []
            }]
        }]
    }))
    env = dict(os.environ)
    env.update(RECOMPDEV_TEST_MODE='1', RECOMPDEV_HOME=str(home),
               PYTHONDONTWRITEBYTECODE='1')
    for attempt in range(3):
        proc = subprocess.run([
            sys.executable, '-B', str(script), 'play', str(rom),
            '--controller-exe', str(controller), '--source-root', str(source),
            '--no-monitor', '--video', 'capture', '--input', 'neutral',
            '--frames', '12', '--steps', '1200000', '--max-recoveries', '4',
            '--timeout', '180', '--allow-synthetic-test-export', '--test-export', str(export)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
           timeout=200)
        if proc.returncode != 0:
            # A TemporaryDirectory is removed on test exit. Include the native
            # subcommand's immutable log in CTest output BEFORE that happens;
            # otherwise Windows/MSVC failures are impossible to diagnose.
            logs=[]
            for session in sorted((home/'RecompDev-Evidence'/'v0.4.9.27'/'live').glob('live-*')):
                for name in ('format.log','initial-translation.log','recovery-0001-translation.log','native-game.log'):
                    path=session/name
                    if path.is_file():
                        data=path.read_text(encoding='utf8',errors='replace')
                        logs.append(f'[{path}]\n{data[-6000:]}')
            raise AssertionError(f'Live controller failed ({proc.returncode}):\n{proc.stdout[-3500:]}\n{proc.stderr[-1500:]}\n'+'\n'.join(logs))
        output = [row.removeprefix('RECOMPDEV_LIVE_EVIDENCE=') for row in proc.stdout.splitlines()
                  if row.startswith('RECOMPDEV_LIVE_EVIDENCE=')]
        assert len(output) == 1, proc.stdout
        session = Path(output[0]); report = json.loads((session / 'session.json').read_text())
        result = report['native_result']
        assert report['status'] == 'FRAME_BUDGET_REACHED_PARITY_UNVERIFIED', report
        assert report['same_guest_process'] is True
        assert (session/'compilations'/'initial-translation-manifest.json').is_file()
        if os.name=='nt':
            scratch_path=Path(report['native_compile_root'])
            assert report['native_compile_scratch'] is True
            assert scratch_path.is_relative_to(Path(os.environ['LOCALAPPDATA'])/'RecompDev'/'nb')
            assert not scratch_path.is_relative_to(session)
            assert not scratch_path.exists(), 'Scratch must be removed after live session'
        else:
            assert report['native_compile_scratch'] is False
        assert result['status'] == 'FRAME_BUDGET_REACHED', result
        assert result['frames'] >= 12, result
        assert 'RECOMPDEV_LIVE_GAME_PROCESS=' in proc.stdout
        if attempt==0:
            assert result['hot_activations']==2,result
            assert [entry['pc'] for entry in report['hot_activations']] == [0x2000,0x2100],report
            assert len(list((session/'control').glob('request-*.json')))==2
            assert len(list((session/'control').glob('activation-*.json')))==2
            assert len(list((session/'control').glob('response-*.json')))==2
            assert all(entry['activation_confirmed'] for entry in report['hot_activations'])
            assert report['cached_activations']==2,report
            assert len(list((session/'control'/'modules').rglob('rd_generated_translation_hot.*')))==2
            assert 'NATIVE_MODULE_ACTIVATED_RESUMING' in (session/'control'/'telemetry.jsonl').read_text()
            assert [entry['cache'] for entry in report['hot_activations']]==['MISS','MISS'],report
            assert 'RECOMPDEV_LIVE_COMPILED_MODULE_CACHE=MISS' in proc.stdout
            assert 'consolidated_library' in report,report
            assert report['consolidated_library']['emitted']>=3,report
            cache=home/'nc'
            assert len(list(cache.rglob('manifest.json')))==2,cache
            for path in cache.rglob('manifest.json'):
                info=json.loads(path.read_text())
                assert info['emitted']>0 and info['generated_sources'],info
            generated=home/'gs'/digest
            assert (generated/'.git').is_dir(),generated
            assert len(list((generated/'m').glob('*/s/translated.cpp')))==2,generated
            assert isinstance(report['generated_source_commit'],str) and len(report['generated_source_commit'])==40,report
            assert len(list(generated.glob('consolidated/*/translated.cpp')))==1,generated
        else:
            # The consolidated game DLL eliminates both missing-code pauses.
            assert result['hot_activations']==0,result
            assert report['hot_activations']==[],report
            assert report['consolidated_preload']['emitted']>=3,report
            assert not list((session/'control').glob('request-*.json'))
            assert not list(session.glob('recovery-*-translation.log'))
            assert 'RECOMPDEV_LIVE_CONSOLIDATED_LIBRARY=HIT' in proc.stdout
            if attempt==1:
                # Simulate a new controller/VDP build: old DLL is incompatible,
                # but the saved source-attested discoveries can be rebuilt.
                pointer=home/'nl'/digest/'current.json'
                old=json.loads(pointer.read_text())
                old['fingerprint']='0'*64
                pointer.write_text(json.dumps(old))
            else:
                assert report['historical_source_rebuild']['frontiers']==2,report
                assert 'RECOMPDEV_LIVE_HISTORY_REBUILT_FROM_SOURCE=2' in proc.stdout,proc.stdout
    print('RECOMPDEV_V27_CONTROLLER_SAME_PROCESS_TWO_RECOVERIES_AND_SOURCE_UPGRADE=PASS')
