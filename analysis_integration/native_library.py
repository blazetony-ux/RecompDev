#!/usr/bin/env python3
"""Controller-owned source/coverage checkpoints for immutable native game modules.

No ROM bytes enter Git. Executable artifacts live in an isolated SHA-indexed
store; reproducible translated C++ and provenance live in a separate per-ROM
Git repository. This module has no Z80 or machine-specific knowledge.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

CACHE_SCHEMA='recompdev.native.compiled.module-cache.v1'
COVERAGE_SCHEMA='recompdev.native.coverage-exclusion.v1'
LIBRARY_SCHEMA='recompdev.native.consolidated.library.v1'
SAFE_SOURCE=re.compile(r'^(?:translated\.cpp|native_part_[0-9]+\.cpp|native_block_export\.cpp|CMakeLists\.txt)$')

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def publish_json(path:Path,doc:dict):
    if path.exists() or path.is_symlink():raise RuntimeError('NATIVE_IMMUTABLE_ARTIFACT_EXISTS')
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.pending')
    with tmp.open('xb') as f:
        f.write((json.dumps(doc,sort_keys=True,indent=2)+'\n').encode())
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def write_evidence_index(path:Path,files):
    """Write a bounded, immutable UTF-8 path index for the native controller.

    No guest bytes or executable native code are put in an index; source and
    bank identity checks remain the responsibility of the native plugins.
    """
    raw=[Path(file) for file in files]
    if any(p.is_symlink() for p in raw):
        raise RuntimeError('NATIVE_EVIDENCE_INDEX_ENTRY_UNSAFE')
    entries=sorted(set(p.resolve(strict=True) for p in raw))
    if len(entries)>512:raise RuntimeError('NATIVE_EVIDENCE_INDEX_ENTRY_LIMIT')
    if path.exists() or path.is_symlink():raise RuntimeError('NATIVE_EVIDENCE_INDEX_EXISTS')
    for entry in entries:
        if (not entry.is_file() or entry.is_symlink() or entry.suffix!='.json'
            or entry.stat().st_size>16*1024*1024 or len(str(entry).encode('utf8'))>2048
            or '\n' in str(entry) or '\r' in str(entry)):
            raise RuntimeError('NATIVE_EVIDENCE_INDEX_ENTRY_UNSAFE')
    data=(''.join(str(entry)+'\n' for entry in entries)).encode('utf8')
    if len(data)>1024*1024:raise RuntimeError('NATIVE_EVIDENCE_INDEX_TOO_LARGE')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as output:
        output.write(data);output.flush();os.fsync(output.fileno())

def read_json(path:Path,max_bytes=2*1024*1024)->dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size>max_bytes:
        raise RuntimeError('NATIVE_ARTIFACT_JSON_UNSAFE')
    doc=json.loads(path.read_text(encoding='utf8'))
    if type(doc)!=dict:raise RuntimeError('NATIVE_ARTIFACT_DOCUMENT_NOT_OBJECT')
    return doc

def coverage_from_manifest(doc:dict,rom_sha:str)->list[dict]:
    if doc.get('schema')!='recompdev.native.pcode.generated.v1' or doc.get('source_sha256')!=rom_sha:
        raise RuntimeError('NATIVE_COVERAGE_SOURCE_OR_SCHEMA_MISMATCH')
    items=doc.get('accepted_instructions')
    if type(items)!=list or len(items)!=doc.get('emitted') or len(items)>100000:
        raise RuntimeError('NATIVE_COVERAGE_INSTRUCTION_COUNT_INVALID')
    found={}
    for a in items:
        if type(a)!=dict or any(type(a.get(k)) is not int for k in ('physical','pc','length')):
            raise RuntimeError('NATIVE_COVERAGE_ENTRY_INVALID')
        phys,pc,length=(a[k] for k in ('physical','pc','length'))
        if not (0<=phys<32*1024*1024 and 0<=pc<0xc000 and 1<=length<=16 and pc+length<=0xc000):
            raise RuntimeError('NATIVE_COVERAGE_ADDRESS_INVALID')
        bs=a.get('bytes_sha256')
        if not isinstance(bs,str) or not re.fullmatch(r'[0-9a-f]{64}',bs):
            raise RuntimeError('NATIVE_COVERAGE_BYTES_SHA_INVALID')
        item={k:a[k] for k in ('physical','pc','length','bytes_sha256')}
        if phys in found:raise RuntimeError('NATIVE_COVERAGE_DUPLICATE')
        found[phys]=item
    return list(found.values())

class Coverage:
    def __init__(self,rom_sha:str):self.rom_sha=rom_sha;self.by_physical={}
    def add(self,items:list[dict]):
        for item in items:
            p=item['physical']
            if p in self.by_physical and self.by_physical[p]!=item:
                raise RuntimeError('NATIVE_COVERAGE_CONFLICT')
            self.by_physical[p]=item
    def entries(self):return [self.by_physical[k] for k in sorted(self.by_physical)]
    def exclusion(self,target:Path):
        publish_json(target,{'schema':COVERAGE_SCHEMA,'source_sha256':self.rom_sha,
                             'accepted_instructions':self.entries()})
        return target

def _safe_parent(directory:Path):
    if directory.is_symlink():raise RuntimeError('NATIVE_STORE_SYMLINK_FORBIDDEN')
    directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink():raise RuntimeError('NATIVE_STORE_SYMLINK_FORBIDDEN')

def commit_cache(root:Path,key:str,fingerprint:str,rom_sha:str,module:Path,source:Path,emitted:int)->Path:
    """Write a complete immutable cache capsule after game-process activation ACK."""
    doc=read_json(source/'translation-manifest.json')
    coverage=coverage_from_manifest(doc,rom_sha)
    if len(coverage)!=emitted:raise RuntimeError('NATIVE_CACHE_EMITTED_COUNT_MISMATCH')
    dest=root/key[:2]/key
    if dest.exists():
        cached=fetch_cache(root,key,fingerprint,rom_sha)
        if cached is not None:return dest
        raise RuntimeError('NATIVE_CACHE_CONFLICT')
    _safe_parent(dest.parent)
    # Write privately first; publish by atomic directory rename after every hash.
    private=dest.with_name(dest.name+'.pending-'+str(os.getpid()))
    private.mkdir(mode=0o700,exist_ok=False)
    try:
        if module.is_symlink() or not module.is_file():raise RuntimeError('NATIVE_CACHE_MODULE_UNSAFE')
        shutil.copyfile(module,private/module.name)
        if sha(private/module.name)!=sha(module):raise RuntimeError('NATIVE_CACHE_MODULE_COPY_MISMATCH')
        sourcefiles={}
        _safe_parent(private/'source')
        for file in sorted(source.iterdir()):
            if not SAFE_SOURCE.fullmatch(file.name):continue
            if not file.is_file() or file.is_symlink() or file.stat().st_size>16*1024*1024:
                raise RuntimeError('NATIVE_CACHE_SOURCE_UNSAFE')
            shutil.copyfile(file,private/'source'/file.name)
            sourcefiles[file.name]=sha(private/'source'/file.name)
        if not sourcefiles or 'translated.cpp' not in sourcefiles or 'native_block_export.cpp' not in sourcefiles or 'CMakeLists.txt' not in sourcefiles:
            raise RuntimeError('NATIVE_CACHE_GENERATED_SOURCE_MISSING')
        shutil.copyfile(source/'translation-manifest.json',private/'translation-manifest.json')
        info={'schema':CACHE_SCHEMA,'key':key,'fingerprint':fingerprint,'source_sha256':rom_sha,
              'filename':module.name,'module_sha256':sha(module),'emitted':emitted,
              'translation_manifest_sha256':sha(private/'translation-manifest.json'),
              'generated_sources':sourcefiles}
        publish_json(private/'manifest.json',info)
        os.replace(private,dest)
    except BaseException:
        shutil.rmtree(private,ignore_errors=True)
        raise
    return dest

def fetch_cache(root:Path,key:str,fingerprint:str,rom_sha:str):
    dest=root/key[:2]/key
    if not dest.exists():return None
    if not dest.is_dir() or dest.is_symlink():raise RuntimeError('NATIVE_CACHE_DIRECTORY_UNSAFE')
    doc=read_json(dest/'manifest.json',64*1024)
    if (doc.get('schema'),doc.get('key'),doc.get('fingerprint'),doc.get('source_sha256'))!=(CACHE_SCHEMA,key,fingerprint,rom_sha):
        raise RuntimeError('NATIVE_CACHE_CONTEXT_MISMATCH')
    name=doc.get('filename')
    if name not in ('rd_generated_translation_hot.dll','rd_generated_translation_hot.so','rd_generated_translation_hot.dylib'):
        raise RuntimeError('NATIVE_CACHE_MODULE_FILENAME_UNSAFE')
    binary=dest/name
    if (not binary.is_file() or binary.is_symlink() or sha(binary)!=doc.get('module_sha256')):
        raise RuntimeError('NATIVE_CACHE_MODULE_SHA_MISMATCH')
    translation=dest/'translation-manifest.json'
    if sha(translation)!=doc.get('translation_manifest_sha256'):
        raise RuntimeError('NATIVE_CACHE_TRANSLATION_MANIFEST_CHANGED')
    coverage=coverage_from_manifest(read_json(translation),rom_sha)
    if len(coverage)!=doc.get('emitted'):raise RuntimeError('NATIVE_CACHE_COVERAGE_MISMATCH')
    for name,digest in doc.get('generated_sources',{}).items():
        if not SAFE_SOURCE.fullmatch(name) or sha(dest/'source'/name)!=digest:
            raise RuntimeError('NATIVE_CACHE_GENERATED_SOURCE_CHANGED')
    return binary,len(coverage),coverage

def history_root(home:Path,rom_sha:str)->Path:
    """Short, ROM-SHA-qualified Git root independent of long evidence paths."""
    if not re.fullmatch(r'[0-9a-f]{64}',rom_sha):
        raise RuntimeError('NATIVE_GENERATED_HISTORY_ROM_HASH_INVALID')
    return home/'gs'/rom_sha

def storage_roots(home:Path,rom_sha:str):
    """Keep persistent native artifacts within legacy Windows MAX_PATH bounds.

    The configured evidence root is for diagnostics, not generated sources or
    binaries. The full ROM SHA, cache key and DLL SHA remain directory names;
    no identity-shortening, permissive Windows registry switch or relocation of
    the canonical RecompDev Git repository is required.
    """
    history=history_root(home,rom_sha)
    cache=home/'nc'
    consolidated=home/'nl'/rom_sha
    if os.name=='nt':
        full='f'*64
        projected=(history/'m'/full/'s'/'native_block_export.cpp',
                   history/'consolidated'/full/'native_block_export.cpp',
                   cache/full[:2]/full/'source'/'native_block_export.cpp',
                   consolidated/full/'rd_generated_translation_hot.dll')
        if any(len(str(p))>=250 for p in projected):
            raise RuntimeError('NATIVE_PERSISTENT_STORE_PATH_TOO_LONG')
    return history,cache,consolidated

def save_generated(history:Path,key:str,cache_capsule:Path,bank_exports:list[Path],seeds:list[Path]):
    """Materialise an audited, binary-free, per-game generated-source worktree."""
    _safe_parent(history)
    _safe_parent(history/'m')
    target=history/'m'/key
    if not target.exists():
        target.mkdir(mode=0o700)
        for name in ('manifest.json','translation-manifest.json'):
            shutil.copyfile(cache_capsule/name,target/name)
        shutil.copytree(cache_capsule/'source',target/'s')
    # Save source discovery for later consolidation of multiple sessions.
    for folder,files in (('exports',bank_exports),('frontiers',seeds)):
        _safe_parent(history/folder)
        for path in files:
            if not path.is_file() or path.is_symlink() or path.stat().st_size>16*1024*1024:
                raise RuntimeError('NATIVE_SOURCE_EVIDENCE_UNSAFE')
            digest=sha(path)
            dest=history/folder/(digest+'.json')
            if not dest.exists():shutil.copyfile(path,dest)
            if sha(dest)!=digest:raise RuntimeError('NATIVE_SOURCE_EVIDENCE_CHANGED')

def git_checkpoint(history:Path,rom_sha:str,fingerprint:str)->str:
    """Use an isolated per-ROM repo, never the RecompDev development repository."""
    git=shutil.which('git')
    if not git:return 'GIT_UNAVAILABLE'
    def cmd(*args):
        result=subprocess.run([git,'-C',str(history),*args],capture_output=True,text=True,timeout=90)
        if result.returncode:
            raise RuntimeError('NATIVE_GIT_COMMAND_FAILED_'+str(args[:2])+': '+result.stderr[-300:])
        return result.stdout.strip()
    if not (history/'.git').exists():cmd('init','--quiet')
    if not (history/'README.md').exists():
        (history/'README.md').write_text('# RecompDev generated source history\n\n'
            'ROM bytes are not stored here. Every module references a validated source SHA-256, '
            'toolchain identity and an immutable compiled artifact.\n\n'
            'Layout: m/<full-module-key>/s/ contains generated C++; exports/ and frontiers/ '
            'retain source-bound analysis; consolidated/ retains unified source.\n')
    publication=history/'compatibility.json'
    record={'schema':'recompdev.native.source-history.v1','rom_sha256':rom_sha,
            'compiler_fingerprint':fingerprint}
    # A new fingerprint represents a new generated-code revision, not a overwrite
    # of existing immutable DLLs. Git preserves the prior source snapshot.
    publication.write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    paths=[p for p in ('README.md','compatibility.json','m','exports','frontiers','consolidated') if (history/p).exists()]
    cmd('add','--',*paths)
    changed=subprocess.run([git,'-C',str(history),'diff','--cached','--quiet'],timeout=30)
    if changed.returncode==1:
        cmd('-c','user.name=RecompDev Generated Source',
            '-c','user.email=recompdev-generated@local.invalid',
            'commit','--quiet','-m','Generated native source checkpoint for '+rom_sha[:12])
    elif changed.returncode!=0:raise RuntimeError('NATIVE_GIT_DIFF_FAILED')
    return cmd('rev-parse','HEAD')

def fetch_library(directory:Path,rom_sha:str,fingerprint:str):
    info=directory/'current.json'
    if not info.exists():return None
    if info.is_symlink():raise RuntimeError('NATIVE_LIBRARY_POINTER_UNSAFE')
    doc=read_json(info,64*1024)
    if (doc.get('schema'),doc.get('source_sha256'))!=(LIBRARY_SCHEMA,rom_sha):
        raise RuntimeError('NATIVE_LIBRARY_CONTEXT_MISMATCH')
    if doc.get('fingerprint')!=fingerprint:
        # Native binaries from an older controller/toolchain must never be
        # hot-loaded under an unproven ABI. Keep the immutable generation and
        # recompile its source-attested findings with the current toolchain.
        return None
    name=doc.get('module')
    if name not in ('rd_generated_translation_hot.dll','rd_generated_translation_hot.so','rd_generated_translation_hot.dylib'):
        raise RuntimeError('NATIVE_LIBRARY_MODULE_NAME_INVALID')
    folder=doc.get('generation')
    if not isinstance(folder,str) or not re.fullmatch(r'[0-9a-f]{64}',folder):
        raise RuntimeError('NATIVE_LIBRARY_GENERATION_INVALID')
    binary=directory/folder/name
    if (directory.is_symlink() or (directory/folder).is_symlink() or
        not binary.is_file() or binary.is_symlink() or sha(binary)!=doc.get('module_sha256')):
        raise RuntimeError('NATIVE_LIBRARY_MODULE_HASH_MISMATCH')
    manifest=directory/folder/'translation-manifest.json'
    if sha(manifest)!=doc.get('translation_manifest_sha256'):
        raise RuntimeError('NATIVE_LIBRARY_COVERAGE_HASH_MISMATCH')
    coverage=coverage_from_manifest(read_json(manifest),rom_sha)
    if len(coverage)!=doc.get('emitted'):raise RuntimeError('NATIVE_LIBRARY_COVERAGE_COUNT_MISMATCH')
    return binary,coverage,doc

def publish_library(directory:Path,rom_sha:str,fingerprint:str,binary:Path,generated:Path,
                    required:list[dict],source_commit:str):
    translated=generated/'translation-manifest.json'
    coverage=coverage_from_manifest(read_json(translated),rom_sha)
    indexed={item['physical']:item for item in coverage}
    if any(indexed.get(item['physical'])!=item for item in required):
        raise RuntimeError('NATIVE_CONSOLIDATION_INCOMPLETE_COVERAGE')
    digest=sha(binary)
    gen=directory/digest
    _safe_parent(directory)
    if not gen.exists():
        gen.mkdir(mode=0o700)
        shutil.copyfile(binary,gen/binary.name)
        shutil.copyfile(translated,gen/'translation-manifest.json')
    if sha(gen/binary.name)!=digest or sha(gen/'translation-manifest.json')!=sha(translated):
        raise RuntimeError('NATIVE_LIBRARY_EXISTING_ARTIFACT_CHANGED')
    if not isinstance(source_commit,str) or not re.fullmatch(r'[0-9a-f]{40}',source_commit):
        raise RuntimeError('NATIVE_LIBRARY_GENERATED_SOURCE_COMMIT_REQUIRED')
    doc={'schema':LIBRARY_SCHEMA,'source_sha256':rom_sha,'fingerprint':fingerprint,
         'generation':digest,'module':binary.name,'module_sha256':digest,'emitted':len(coverage),
         'translation_manifest_sha256':sha(translated),'generated_source_commit':source_commit}
    # Validate first, then replace only a tiny pointer atomically; old DLLs remain.
    temp=directory/'current.json.pending'
    temp.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
    os.replace(temp,directory/'current.json')
    return doc
