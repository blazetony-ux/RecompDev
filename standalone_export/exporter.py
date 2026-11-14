"""Hardware-neutral standalone native application export and verification.

Build-time toolchain and source checkout are required on the development host.
The exported native binary requires neither those tools nor an external ROM.
Game-data embedding requires explicit user rights confirmation. This exporter
currently implements one versioned source adapter, not cross-ISA qualification.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

try:
    from . import nativepilot_adapter
except ImportError:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from standalone_export import nativepilot_adapter

SCHEMA = 'recompdev.standalone.export.v1'
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_PROJECT_BYTES = 256 * 1024 * 1024
BUILD_TIMEOUT = 600


def sha256(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1048576), b''):
            hash_.update(block)
    return hash_.hexdigest()


def safe_project(project: Path) -> None:
    if not project.is_dir() or project.is_symlink():
        raise ValueError('EXPORT_SOURCE_PROJECT_MISSING_OR_SYMLINK')
    total = 0
    for item in project.rglob('*'):
        if item.is_symlink():
            raise ValueError('EXPORT_PROJECT_SYMLINK_FORBIDDEN: '+str(item.relative_to(project)))
        if item.is_file():
            total += item.stat().st_size
            if total > MAX_PROJECT_BYTES:
                raise ValueError('EXPORT_PROJECT_SIZE_LIMIT_EXCEEDED')


def run(command: list[str], cwd: Path, timeout: int = BUILD_TIMEOUT) -> str:
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode:
        raise RuntimeError('EXPORT_NATIVE_BUILD_FAILED: '+repr(command)+'\n'+
                           proc.stdout[-6000:]+'\n'+proc.stderr[-6000:])
    return proc.stdout[-6000:]


def target_name() -> str:
    # The native host toolchain selects its own target OS. Cross-compilation is
    # deliberately not assumed without a separate attested toolchain contract.
    return platform.system().lower()+'-'+platform.machine().lower()


def build(*, project: Path, data: Path, output: Path, rights_confirmed: bool,
          self_test: bool = True, cmake: str = 'cmake') -> dict:
    if not rights_confirmed:
        raise ValueError('EXPORT_RIGHTS_CONFIRMATION_REQUIRED')
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('EXPORT_DESTINATION_EXISTS_REFUSING_TO_OVERWRITE')
    if project.is_symlink() or data.is_symlink():
        raise ValueError('EXPORT_SOURCE_SYMLINK_FORBIDDEN')
    project = project.resolve(strict=True)
    data = data.resolve(strict=True)
    safe_project(project)
    if not data.is_file() or data.is_symlink() or data.stat().st_size==0 or data.stat().st_size>MAX_SOURCE_BYTES:
        raise ValueError('EXPORT_SOURCE_DATA_INVALID_OR_TOO_LARGE')
    if not data.is_relative_to(project):
        # No restriction on where the owner keeps their authorised input;
        # input is read once, never copied into output as a separate ROM.
        pass
    source_bytes = data.read_bytes()
    qualification = nativepilot_adapter.validate(project, source_bytes)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('EXPORT_DESTINATION_EXISTS_REFUSING_TO_OVERWRITE')
    if not output.parent.is_dir():
        raise ValueError('EXPORT_DESTINATION_PARENT_MISSING')
    if output.parent.is_symlink():
        raise ValueError('EXPORT_DESTINATION_PARENT_SYMLINK')
    # Independent short build workspace; do not stage generated C++ beneath
    # deeply nested historical evidence folders on Windows.
    with tempfile.TemporaryDirectory(prefix='rdx-', dir=output.parent) as temp:
        base=Path(temp)
        source=base/'s'
        source.mkdir()
        nativepilot_adapter.stage(project,source,source_bytes)
        if sha256(source/'translated.cpp') != qualification['translated_cpp_sha256']:
            raise RuntimeError('EXPORT_TRANSLATED_SOURCE_CHANGED')
        b=base/'b'
        command=[cmake,'-S',str(source),'-B',str(b),'-DCMAKE_BUILD_TYPE=Release']
        # Do not force a VS platform on non-VS generators. Host's toolchain
        # produces native Win64 when invoked from a Windows x64 build environment.
        run(command,base)
        run([cmake,'--build',str(b),'--config','Release','--target','RecompDevStandalone','--parallel','2'],base)
        filename='RecompDevStandalone.exe' if os.name=='nt' else 'RecompDevStandalone'
        candidates=[b/'Release'/filename,b/filename]
        binary=next((file for file in candidates if file.is_file()),None)
        if binary is None:
            raise RuntimeError('EXPORT_NATIVE_EXECUTABLE_NOT_CREATED')
        packaged=base/'package'
        packaged.mkdir()
        shutil.copyfile(binary,packaged/filename)
        if not os.name=='nt':
            (packaged/filename).chmod((packaged/filename).stat().st_mode|0o111)
        report={
            'schema':SCHEMA,'status':'BUILT_UNQUALIFIED',
            'target':target_name(),'adapter':qualification['adapter'],
            'native_executable':filename,'native_executable_sha256':sha256(packaged/filename),
            'native_executable_bytes':(packaged/filename).stat().st_size,
            'source_data_sha256':qualification['source_sha256'],
            'source_data_bytes':qualification['source_size'],
            'source_data_storage':'embedded_in_native_executable',
            'rights_confirmed_by_export_operator':True,
            'translated_cpp_sha256':qualification['translated_cpp_sha256'],
            'generation_sha256':qualification['generation_sha256'],
            'translated_instructions':qualification['translated_instructions'],
            'unsupported_instructions':qualification['unsupported_instructions'],
            'coverage_qualification':'NOT_ESTABLISHED',
            'hardware_parity':'NOT_TESTED',
            'independent_gameplay_qualification':'NOT_TESTED',
            'compiler_required_on_target':False,
            'controller_required_on_target':False,
            'separate_source_binary_required_on_target':False,
            'external_game_plugin_dependencies':[],
            'note':'Experimental standalone native application. A successful export is not evidence of complete translated coverage or hardware parity.'
        }
        if self_test:
            # Launch with no access to the original source/project. Only
            # the executable and standard OS facilities are present in cwd.
            probe=base/'isolated-run'
            probe.mkdir()
            args=[str(packaged/filename),str(probe/'smoke'),'3','1000','-',
                  '--video','capture','--audio','capture','--input','neutral']
            test=subprocess.run(args,cwd=probe,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                text=True,timeout=45)
            marker=next((line for line in test.stdout.splitlines() if line.startswith('NATIVE_APP_RESULT=')),None)
            if test.returncode or not marker:
                raise RuntimeError('EXPORT_ISOLATED_NATIVE_LAUNCH_FAILED: '+test.stderr[-1800:]+' '+test.stdout[-1800:])
            native=json.loads(marker.partition('=')[2]); steps=native.get('native_steps',0)
            if not isinstance(steps,int) or steps<1:
                raise RuntimeError('EXPORT_ISOLATED_NO_NATIVE_STEPS')
            report['isolated_native_launch']={'status':'PASS','native_steps':steps,
                                               'terminal_status':native.get('status'),
                                               'external_source_supplied':False}
        else:
            report['isolated_native_launch']={'status':'NOT_TESTED'}
        (packaged/'export-manifest.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf8')
        (packaged/'README.txt').write_text(
            'RecompDev standalone native export v1\n\n'
            'Run RecompDevStandalone.exe on Windows, or RecompDevStandalone on your build OS.\n'
            'No external ROM file, controller, Python or installed compiler is required to run.\n'
            'The game source/data was embedded with your explicit rights confirmation.\n'
            'Native coverage and hardware parity are NOT qualified.\n'
            'For headless capture: RecompDevStandalone <output-prefix> <frames> <steps> - '
            '--video capture --audio capture --input neutral\n'
            'Use `RecompDev export verify --bundle <folder>` before distribution.\n',
            encoding='utf8')
        packaged.rename(output)
    return report


def verify(bundle: Path, expected_manifest_sha256: str | None = None) -> dict:
    if not bundle.is_dir() or bundle.is_symlink():
        raise ValueError('EXPORT_BUNDLE_DIRECTORY_MISSING')
    manifest_file=bundle/'export-manifest.json'
    if not manifest_file.is_file() or manifest_file.is_symlink():
        raise ValueError('EXPORT_BUNDLE_MANIFEST_MISSING')
    actual_manifest_sha256=sha256(manifest_file)
    if expected_manifest_sha256 is not None and actual_manifest_sha256.lower()!=expected_manifest_sha256.lower():
        raise ValueError('EXPORT_MANIFEST_PIN_MISMATCH')
    report=json.loads(manifest_file.read_text(encoding='utf8'))
    if report.get('schema')!=SCHEMA or report.get('status')!='BUILT_UNQUALIFIED':
        raise ValueError('EXPORT_BUNDLE_SCHEMA_OR_STATUS_INVALID')
    binary=report.get('native_executable')
    if binary not in ('RecompDevStandalone.exe','RecompDevStandalone'):
        raise ValueError('EXPORT_EXECUTABLE_NAME_INVALID')
    expected={'export-manifest.json','README.txt',binary}
    actual={p.name for p in bundle.iterdir()}
    if actual!=expected or any(p.is_symlink() or not p.is_file() for p in bundle.iterdir()):
        raise ValueError('EXPORT_BUNDLE_FILES_INVALID')
    if sha256(bundle/binary)!=report['native_executable_sha256']:
        raise ValueError('EXPORT_EXECUTABLE_HASH_MISMATCH')
    if (bundle/binary).stat().st_size != report['native_executable_bytes']:
        raise ValueError('EXPORT_EXECUTABLE_SIZE_MISMATCH')
    if (report.get('controller_required_on_target') is not False or
        report.get('compiler_required_on_target') is not False or
        report.get('source_data_storage')!='embedded_in_native_executable'):
        raise ValueError('EXPORT_BUNDLE_CONTRACT_INCOMPLETE')
    return {'status':'VERIFIED','schema':SCHEMA,'target':report['target'],
            'native_executable':binary,'native_sha256':report['native_executable_sha256'],
            'manifest_sha256':actual_manifest_sha256,
            'coverage_qualification':report['coverage_qualification'],
            'hardware_parity':report['hardware_parity']}


def main(argv=None) -> int:
    cli=argparse.ArgumentParser(description='RecompDev source-attested standalone native application export')
    verbs=cli.add_subparsers(dest='action',required=True)
    make=verbs.add_parser('build',help='compile independent app, embed authorised source data and verify isolated launch')
    make.add_argument('--project',type=Path,required=True)
    make.add_argument('--source-data',type=Path,required=True)
    make.add_argument('--out',type=Path,required=True)
    make.add_argument('--rights-confirmed',action='store_true',help='you are authorised to embed the supplied game data into the distributed executable')
    make.add_argument('--no-self-test',action='store_true',help='skip isolated native-run acceptance (reported NOT_TESTED)')
    make.add_argument('--cmake',default='cmake')
    demo=verbs.add_parser('demo',help='export the bundled rights-cleared synthetic instruction-loop fixture')
    demo.add_argument('--out',type=Path,required=True)
    demo.add_argument('--cmake',default='cmake')
    check=verbs.add_parser('verify',help='verify a self-contained export without original sources')
    check.add_argument('--bundle',type=Path,required=True)
    check.add_argument('--expected-manifest-sha256',default=None)
    args=cli.parse_args(argv)
    try:
        if args.action=='build':
            result=build(project=args.project,data=args.source_data,output=args.out,
                         rights_confirmed=args.rights_confirmed,self_test=not args.no_self_test,
                         cmake=args.cmake)
        elif args.action=='demo':
            from standalone_export.demo import build_demo
            result=build_demo(args.out,cmake=args.cmake)
        else:
            result=verify(args.bundle,args.expected_manifest_sha256)
        print('RECOMPDEV_STANDALONE_EXPORT='+json.dumps(result,sort_keys=True))
        return 0
    except (OSError,ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print('RECOMPDEV_STANDALONE_EXPORT_ERROR='+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
