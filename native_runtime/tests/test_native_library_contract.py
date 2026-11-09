"""Fast fail-closed and durable Git tests for platform-neutral game modules."""
import hashlib,json,sys,tempfile
from pathlib import Path, PureWindowsPath
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from analysis_integration import native_library as lib

def digest(data):return hashlib.sha256(data).hexdigest()
def rejected(callback):
    try:callback()
    except (RuntimeError,ValueError):return
    raise AssertionError('Expected invalid native source or binary to be rejected')

with tempfile.TemporaryDirectory(prefix='rd27-module-governance-') as tmp:
    root=Path(tmp)
    rom_sha=digest(b'fictional ROM identifier; no game bytes stored')
    key=digest(b'cache key')
    fp=digest(b'build identities')
    emitted=[{'pc':0,'physical':0,'length':1,'bytes_sha256':digest(b'\0')}]
    manifest={'schema':'recompdev.native.pcode.generated.v1',
              'source_sha256':rom_sha,'emitted':1,'accepted_instructions':emitted}
    source=root/'translation';source.mkdir()
    lib.publish_json(source/'translation-manifest.json',manifest)
    for name in ('translated.cpp','native_block_export.cpp','CMakeLists.txt'):
        (source/name).write_text('/* checked source artifact */\n')
    mod=root/'rd_generated_translation_hot.dll';mod.write_bytes(b'pretend compiled module for SHA contract')
    store=root/'cache'
    capsule=lib.commit_cache(store,key,fp,rom_sha,mod,source,1)
    hit=lib.fetch_cache(store,key,fp,rom_sha)
    assert hit and hit[1]==1 and hit[2]==emitted,hit
    rejected(lambda:lib.fetch_cache(store,key,digest(b'other compiler'),rom_sha))
    rejected(lambda:lib.fetch_cache(store,key,fp,digest(b'other game')))
    cov=lib.Coverage(rom_sha);cov.add(emitted)
    excluded=cov.exclusion(root/'excluded.json')
    assert lib.read_json(excluded)['accepted_instructions']==emitted
    rejected(lambda:cov.add([{'pc':2,'physical':0,'length':1,'bytes_sha256':digest(b'\2')}]))
    bad=dict(manifest);bad['source_sha256']=digest(b'bad')
    rejected(lambda:lib.coverage_from_manifest(bad,rom_sha))
    history=lib.history_root(root,rom_sha)
    assert lib.storage_roots(root,rom_sha)==(history,root/'nc',root/'nl'/rom_sha)
    assert not (history/'m').exists()
    # Regress the exact legacy Windows MAX_PATH class without needing MSVC on
    # the Linux builder. Two full 64-digit identities must still fit at depth.
    simulated=PureWindowsPath(r'C:\Users\tony\AppData\Local\Temp\rd-v27-controller-autonomous-abcdefgh\home')
    full='f'*64
    for nested in (simulated/'gs'/rom_sha/'m'/full/'s'/'native_block_export.cpp',
                   simulated/'gs'/rom_sha/'consolidated'/full/'native_block_export.cpp',
                   simulated/'nc'/full[:2]/full/'source'/'native_block_export.cpp',
                   simulated/'nl'/rom_sha/full/'rd_generated_translation_hot.dll'):
        assert len(str(nested))<250,(len(str(nested)),nested)
    source_seed=root/'frontier.json';source_seed.write_text('{"source":"synthetic"}\n')
    lib.save_generated(history,key,capsule,[],[source_seed])
    assert (history/'m'/key/'s'/'translated.cpp').is_file()
    commit=lib.git_checkpoint(history,rom_sha,fp)
    assert commit=='GIT_UNAVAILABLE' or (len(commit)==40 and (history/'.git').is_dir())
    generated=root/'consolidated';generated.mkdir()
    lib.publish_json(generated/'translation-manifest.json',manifest)
    if commit!='GIT_UNAVAILABLE':
        publication=lib.publish_library(root/'libraries',rom_sha,fp,mod,generated,emitted,commit)
        assert publication['generated_source_commit']==commit
        result=lib.fetch_library(root/'libraries',rom_sha,fp)
        assert result[1]==emitted and result[2]['module_sha256']==digest(mod.read_bytes())
        rejected(lambda:lib.fetch_library(root/'libraries',digest(b'wrong rom'),fp))
        # A different compiler/runtime fingerprint is a safe cache MISS: never
        # load incompatible native code, but retain the old generation so its
        # source-attested findings can be rebuilt with the new toolchain.
        assert lib.fetch_library(root/'libraries',rom_sha,digest(b'wrong build')) is None
        assert lib.fetch_library(root/'libraries',rom_sha,fp)[2]['generation']==publication['generation']
        (root/'libraries'/publication['generation']/mod.name).write_bytes(b'bitrot')
        rejected(lambda:lib.fetch_library(root/'libraries',rom_sha,fp))
    (capsule/mod.name).write_bytes(b'corrupt')
    rejected(lambda:lib.fetch_cache(store,key,fp,rom_sha))
    assert not list(history.rglob('*.sms'))
    print('RECOMPDEV_NATIVE_LIBRARY_GOVERNANCE=PASS')
