"""Real Git integration tests for per-ROM shared-main publication and restore."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from analysis_integration import generated_source_sync as sync

SHA_A='a'*64
SHA_B='b'*64


def git(path, *args):
    process=subprocess.run(['git','-C',str(path),*args],capture_output=True,text=True)
    if process.returncode:
        raise AssertionError((args,process.stderr,process.stdout))
    return process.stdout.strip()


class GeneratedSourceSync(unittest.TestCase):
    def setUp(self):
        self.sandbox=tempfile.TemporaryDirectory()
        self.base=Path(self.sandbox.name)
        self.home=self.base/'home'
        self.origin=self.base/'remote.git'
        self.central=self.base/'shared'
        git(self.base,'init','--bare',str(self.origin))
        git(self.base,'clone',str(self.origin),str(self.central))
        git(self.central,'checkout','-b','main')
        git(self.central,'-c','user.name=Fixture','-c','user.email=fixture@example.test',
            'commit','--allow-empty','-m','Initialize shared main')
        git(self.central,'push','origin','main')
        sync.setup(self.home,self.central)

    def tearDown(self):
        self.sandbox.cleanup()

    def game(self,sha,content='a'):
        root=self.home/'gs'/sha
        root.mkdir(parents=True,exist_ok=True)
        git(root,'init','-b','main')
        (root/'m'/('1'*64)/'s').mkdir(parents=True)
        (root/'m'/('1'*64)/'s'/'translated.cpp').write_text('// '+content+'\n')
        (root/'compatibility.json').write_text(json.dumps({'rom_sha256':sha,'schema':'recompdev.native.source-history.v1'})+'\n')
        git(root,'add','.')
        git(root,'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m','first generated')
        return root

    def test_two_roms_one_main_preserved_history_and_restore(self):
        a=self.game(SHA_A)
        b=self.game(SHA_B)
        a_first=git(a,'rev-parse','HEAD')
        b_first=git(b,'rev-parse','HEAD')
        sync.mark_pending(self.home,SHA_A,a_first)
        sync.mark_pending(self.home,SHA_B,b_first)
        published=sync.publish(self.home)
        self.assertEqual(published['status'],'PUBLISHED')
        self.assertEqual(published['roms'],2)
        for commit in (a_first,b_first):
            self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',commit,'HEAD'),0)
        self.assertEqual(git(self.central,'branch','--show-current'),'main')
        self.assertEqual(git(self.central,'rev-parse','HEAD'),git(self.central,'ls-remote','origin','refs/heads/main').split()[0])
        # A later game checkpoint updates the same shared branch, not a new one.
        (a/'m'/('2'*64)/'s').mkdir(parents=True)
        (a/'m'/('2'*64)/'s'/'native_part_0.cpp').write_text('// new\n')
        git(a,'add','.')
        git(a,'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m','second module')
        a_new=git(a,'rev-parse','HEAD')
        sync.mark_pending(self.home,SHA_A,a_new)
        self.assertEqual(sync.publish(self.home,SHA_A)['status'],'PUBLISHED')
        self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',a_first,'HEAD'),0)
        self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',a_new,'HEAD'),0)
        self.assertFalse(sync.pending_path(self.home,SHA_A).exists())
        # Upgrade/reinstall: pull both exact original game histories into new home.
        second=self.base/'new-install'
        sync.setup(second,self.central)
        restored=sync.restore_all(second)
        self.assertEqual(restored['status'],'RESTORED')
        self.assertEqual(restored['restored'],2)
        self.assertEqual(git(second/'gs'/SHA_A,'rev-parse','HEAD'),a_new)
        self.assertEqual(git(second/'gs'/SHA_B,'rev-parse','HEAD'),b_first)
        self.assertEqual(sync.restore_all(second)['already'],2)

    def test_failed_push_keeps_local_history_and_pending(self):
        a=self.game(SHA_A)
        commit=git(a,'rev-parse','HEAD')
        sync.mark_pending(self.home,SHA_A,commit)
        git(self.central,'remote','set-url','origin',str(self.base/'missing.git'))
        with self.assertRaises(sync.SyncError):
            sync.publish(self.home)
        self.assertTrue(sync.pending_path(self.home,SHA_A).exists())
        self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',commit,'HEAD'),0)
        git(self.central,'remote','set-url','origin',str(self.origin))
        self.assertEqual(sync.publish(self.home)['status'],'PUBLISHED')
        self.assertFalse(sync.pending_path(self.home,SHA_A).exists())

    def test_pre_v28_unsquashed_subtree_restores_original_commit_without_provenance(self):
        existing=self.game(SHA_A)
        original=git(existing,'rev-parse','HEAD')
        git(self.central,'-c','user.name=Fixture','-c','user.email=fixture@example.test',
            'subtree','add','--prefix=generated/roms/'+SHA_A,str(existing),'HEAD','-m','manual pre-v28 import')
        git(self.central,'push','origin','main')
        self.assertFalse((self.central/'generated'/'provenance').exists())
        fresh=self.base/'fresh-home'
        sync.setup(fresh,self.central)
        result=sync.restore_all(fresh)
        self.assertEqual(result['legacy_subtrees_inferred'],1)
        self.assertEqual(result['restored'],1)
        self.assertEqual(git(fresh/'gs'/SHA_A,'rev-parse','HEAD'),original)
        self.assertEqual(sync.publish(fresh)['status'],'PUBLISHED')
        self.assertTrue((self.central/'generated'/'provenance'/(SHA_A+'.json')).is_file())

    def test_bad_source_or_mismatched_identity_rejected(self):
        game=self.game(SHA_A)
        (game/'bad.dll').write_bytes(b'not allowed')
        git(game,'add','bad.dll')
        git(game,'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m','bad')
        with self.assertRaisesRegex(sync.SyncError,'SYNC_SOURCE_PATH_REJECTED'):
            sync.publish(self.home,SHA_A)

    def test_local_unpublished_commit_is_not_clobbered_by_install_restore(self):
        game=self.game(SHA_A)
        sync.publish(self.home)
        old=git(game,'rev-parse','HEAD')
        (game/'m'/('2'*64)/'s').mkdir(parents=True)
        (game/'m'/('2'*64)/'s'/'translated.cpp').write_text('// unpublished\n')
        git(game,'add','.')
        git(game,'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m','unpublished')
        newer=git(game,'rev-parse','HEAD')
        result=sync.restore_all(self.home)
        self.assertEqual(result['local_ahead'],1)
        self.assertEqual(git(game,'rev-parse','HEAD'),newer)
        self.assertNotEqual(old,newer)
        self.assertTrue(sync.pending_path(self.home,SHA_A).is_file())
        self.assertEqual(sync.publish(self.home)['status'],'PUBLISHED')
        self.assertEqual(sync.restore_all(self.home)['already'],1)

    def test_restore_does_not_overwrite_local_uncommitted_changes(self):
        game=self.game(SHA_A)
        sync.publish(self.home)
        (game/'compatibility.json').write_text('{}\n')
        with self.assertRaisesRegex(sync.SyncError,'SYNC_LOCAL_SOURCE_DIRTY'):
            sync.restore_all(self.home)


if __name__=='__main__':
    unittest.main()
