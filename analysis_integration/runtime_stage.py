#!/usr/bin/env python3
"""Hardware-neutral staging of a SHA-verified native runtime *candidate*.

This command never changes the active runtime, a controller binary, or a DLL
lockfile. Staged images are immutable; activation and rollback require a later
separately qualified transaction. No guest/ROM data are copied into Git.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid

SCHEMA = 'recompdev.runtime.staged-image.v1'
RELEASE = re.compile(r'^workspace/v\d+\.\d+\.\d+\.\d+$')
COMPONENT = re.compile(r'^(?:controller|rd_[a-z0-9_]+)$')
SHA = re.compile(r'^[0-9a-f]{64}$')
MAX_BIN = 512 * 1024 * 1024

class StageError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fd:
        for chunk in iter(lambda: fd.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_inventory(path: Path) -> list[dict]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 500000:
        raise StageError('RUNTIME_INVENTORY_INVALID')
    data = json.loads(path.read_text('utf-8'))
    if not isinstance(data, list) or not data or len(data) > 128:
        raise StageError('RUNTIME_INVENTORY_FORMAT_INVALID')
    result = []
    names = set()
    for item in data:
        if not isinstance(item, dict):
            raise StageError('RUNTIME_COMPONENT_INVALID')
        component = item.get('component')
        name = item.get('file')
        digest = item.get('sha256')
        version = item.get('version')
        if not isinstance(component,str) or not COMPONENT.fullmatch(component) or component in names:
            raise StageError('RUNTIME_COMPONENT_IDENTITY_INVALID')
        expected = 'RecompDev.exe' if component == 'controller' else component + '.dll'
        if name != expected or not isinstance(digest,str) or not SHA.fullmatch(digest.lower()):
            raise StageError('RUNTIME_COMPONENT_HASH_OR_FILENAME_INVALID')
        if not isinstance(version,str) or not re.fullmatch(r'\d+(?:\.\d+){1,3}',version):
            raise StageError('RUNTIME_COMPONENT_VERSION_INVALID')
        raw = item.get('path')
        if not isinstance(raw,str) or not raw:
            raise StageError('RUNTIME_COMPONENT_SOURCE_PATH_INVALID')
        source = Path(raw)
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BIN:
            raise StageError('RUNTIME_COMPONENT_SOURCE_UNSAFE')
        if sha256(source) != digest.lower():
            raise StageError('RUNTIME_COMPONENT_SOURCE_HASH_MISMATCH')
        names.add(component)
        result.append({'component':component,'version':version,'file':name,
                       'sha256':digest.lower(),'size':source.stat().st_size,'source':source})
    if 'controller' not in names:
        raise StageError('RUNTIME_CONTROLLER_REQUIRED')
    return result


def stage(inventory: Path, destination: Path, release: str) -> dict:
    if not RELEASE.fullmatch(release):
        raise StageError('RUNTIME_RELEASE_ID_INVALID')
    image = safe_inventory(inventory)
    if destination.exists() or destination.is_symlink():
        raise StageError('RUNTIME_STAGED_IMAGE_ALREADY_EXISTS')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.parent.is_symlink():
        raise StageError('RUNTIME_PARENT_SYMLINK_UNSAFE')
    temp = destination.with_name('.'+destination.name+'.stage-'+uuid.uuid4().hex[:12])
    try:
        temp.mkdir()
        exported=[]
        for binary in image:
            target = temp / binary['file']
            with binary['source'].open('rb') as source, target.open('xb') as output:
                shutil.copyfileobj(source,output,1024*1024)
                output.flush();os.fsync(output.fileno())
            if sha256(target) != binary['sha256']:
                raise StageError('RUNTIME_STAGED_COPY_MISMATCH')
            exported.append({key:binary[key] for key in ('component','version','file','sha256','size')})
        manifest={'schema':SCHEMA,'release':release,'runtime_qualified':False,
                  'activation_allowed':False,'components':exported}
        (temp/'image-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        os.rename(temp,destination)  # no overwrite; outside active runtime root
        return {'status':'STAGED_NOT_ACTIVATED','release':release,'components':len(exported),
                'destination':str(destination)}
    finally:
        if temp.exists():shutil.rmtree(temp)


def verify(destination: Path, inventory: Path | None = None) -> dict:
    manifest=destination/'image-manifest.json'
    if destination.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        raise StageError('RUNTIME_STAGE_MANIFEST_MISSING')
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if (data.get('schema') != SCHEMA or data.get('runtime_qualified') is not False or
            data.get('activation_allowed') is not False or
            not isinstance(data.get('release'),str) or not RELEASE.fullmatch(data['release'])):
        raise StageError('RUNTIME_STAGE_POLICY_INVALID')
    records=data.get('components')
    if not isinstance(records,list) or not records or len(records)>128:
        raise StageError('RUNTIME_STAGE_RECORDS_INVALID')
    expected={'image-manifest.json'}
    for item in records:
        if not isinstance(item,dict):raise StageError('RUNTIME_STAGE_RECORD_INVALID')
        component=item.get('component');name=item.get('file');digest=item.get('sha256')
        if not isinstance(component,str) or not COMPONENT.fullmatch(component):
            raise StageError('RUNTIME_STAGE_COMPONENT_INVALID')
        if name != ('RecompDev.exe' if component=='controller' else component+'.dll'):
            raise StageError('RUNTIME_STAGE_FILENAME_INVALID')
        if not isinstance(digest,str) or not SHA.fullmatch(digest):
            raise StageError('RUNTIME_STAGE_DIGEST_INVALID')
        if name in expected:raise StageError('RUNTIME_STAGE_DUPLICATE')
        path=destination/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=item.get('size') or sha256(path)!=digest:
            raise StageError('RUNTIME_STAGE_BINARY_CHANGED')
        expected.add(name)
    if 'RecompDev.exe' not in expected:
        raise StageError('RUNTIME_STAGE_CONTROLLER_MISSING')
    if {p.name for p in destination.iterdir()}!=expected:
        raise StageError('RUNTIME_STAGE_UNEXPECTED_FILE')
    if inventory is not None:
        # Compare against the installer's independent freshly generated
        # SHA inventory, not just hashes in the staged JSON itself.
        originals=safe_inventory(inventory)
        recorded={x['component']:(x['sha256'],x['version'],x['size']) for x in records}
        expected_records={x['component']:(x['sha256'],x['version'],x['size']) for x in originals}
        if recorded != expected_records:
            raise StageError('RUNTIME_STAGE_INVENTORY_MISMATCH')
    return {'status':'VERIFIED_NOT_ACTIVATED','release':data['release'],'components':len(records)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    create=sub.add_parser('stage');create.add_argument('--inventory',type=Path,required=True)
    create.add_argument('--destination',type=Path,required=True);create.add_argument('--release',required=True)
    check=sub.add_parser('verify');check.add_argument('--destination',type=Path,required=True)
    check.add_argument('--inventory',type=Path)
    args=p.parse_args(argv)
    try:
        result=(stage(args.inventory,args.destination,args.release) if args.action=='stage'
                else verify(args.destination,args.inventory))
        print('RECOMPDEV_RUNTIME_STAGE='+json.dumps(result,sort_keys=True),flush=True)
        return 0
    except (StageError,OSError,ValueError,KeyError,TypeError) as exc:
        print('RECOMPDEV_RUNTIME_STAGE=BLOCKED: '+str(exc)[:250],flush=True)
        return 2

if __name__=='__main__':sys.exit(main())
