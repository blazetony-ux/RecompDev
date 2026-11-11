"""Reproduce append-only Shinobi consolidation in the shared Git history."""
import json
from pathlib import Path
import unittest
from analysis_integration import generated_source_sync as sync
from analysis_integration.tests.test_v04928_generated_source_sync import GeneratedSourceSync, git, SHA_A

class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.fixture = GeneratedSourceSync('test_two_roms_one_main_preserved_history_and_restore')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.home=self.fixture.home; self.base=self.fixture.base; self.central=self.fixture.central
        self.game_source = self.fixture.game(SHA_A)
        sync.publish(self.home)
        self.old_commit=git(self.game_source,'rev-parse','HEAD')
        self.old_shared=git(self.central,'rev-parse','HEAD')
        self.pointer=self.central/'generated'/'provenance'/(SHA_A+'.json')
        self.old_provenance=json.loads(self.pointer.read_text())

    def add_consolidated(self):
        folder=self.central/'generated'/'roms'/SHA_A/'consolidated'/('8'*64)
        folder.mkdir(parents=True)
        for filename in ('translated.cpp','native_part_0.cpp','native_part_1.cpp','CMakeLists.txt'):
            (folder/filename).write_text('// new generated native\n')
        git(self.central,'add','.')
        git(self.central,'-c','user.name=Fixture','-c','user.email=fixture@test.invalid',
            'commit','-m','Generated native source checkpoint')
        git(self.central,'-c','user.name=Fixture','-c','user.email=fixture@test.invalid',
            'commit','--allow-empty','-m','Update generated source history')
        return git(self.central,'rev-parse','HEAD:generated/roms/'+SHA_A)

    def test_restore_reconciles_append_only_and_preserves_history(self):
        expected=self.add_consolidated()
        self.assertEqual(json.loads(self.pointer.read_text()),self.old_provenance)
        before=git(self.central,'rev-parse','HEAD')
        result=sync.restore_all(self.home)
        self.assertEqual(result['status'],'RESTORED')
        self.assertEqual(result['reconciled'],1)
        self.assertTrue(sync.pending_path(self.home,SHA_A).is_file())
        new=json.loads(self.pointer.read_text())
        self.assertEqual(new['source_tree'],expected)
        self.assertEqual(git(self.central,'rev-parse',new['source_commit']+'^{tree}'),expected)
        self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',self.old_commit,new['source_commit']),0)
        self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',before,'HEAD'),0)
        self.assertEqual(sync.code(self.central,'merge-base','--is-ancestor',new['source_commit'],'HEAD'),0)
        self.assertEqual(git(self.game_source,'rev-parse','HEAD'),new['source_commit'])
        self.assertEqual(sync.restore_all(self.home)['already'],1)
        self.assertEqual(sync.publish(self.home,SHA_A)['status'],'PUBLISHED')
        self.assertEqual(sync.pending_items(self.home),{})
        fresh=self.base/'fresh-home';sync.setup(fresh,self.central)
        self.assertEqual(sync.restore_all(fresh)['restored'],1)
        self.assertEqual(git(fresh/'gs'/SHA_A,'rev-parse','HEAD'),new['source_commit'])

    def test_modified_existing_code_refused_without_touching_history(self):
        file=self.central/'generated'/'roms'/SHA_A/'m'/('1'*64)/'s'/'translated.cpp'
        file.write_text('// mutated old code\n')
        git(self.central,'add','.')
        git(self.central,'-c','user.name=Fixture','-c','user.email=fixture@test.invalid',
            'commit','-m','Mutation')
        prior=git(self.central,'rev-parse','HEAD')
        with self.assertRaisesRegex(sync.SyncError,'SYNC_RECONCILE_NON_APPEND_ONLY'):
            sync.restore_all(self.home)
        self.assertEqual(git(self.central,'rev-parse','HEAD'),prior)
        self.assertEqual(json.loads(self.pointer.read_text()),self.old_provenance)

    def test_reconcile_keeps_local_ahead_source_unmodified(self):
        expected=self.add_consolidated()
        # Reconciled shared history may be newer than an independent unpublished local change.
        f=self.game_source/'m'/('1'*64)/'s'/'translated.cpp'
        f.write_text('// locally changed code\n')
        git(self.game_source,'add','.')
        git(self.game_source,'-c','user.name=Fixture','-c','user.email=fixture@test.invalid',
            'commit','-m','local unpublished independent')
        head=git(self.game_source,'rev-parse','HEAD')
        with self.assertRaisesRegex(sync.SyncError,'SYNC_LOCAL_AND_REMOTE_HISTORY_DIVERGED'):
            sync.restore_all(self.home)
        self.assertEqual(git(self.game_source,'rev-parse','HEAD'),head)
        self.assertEqual(git(self.central,'rev-parse','HEAD:generated/roms/'+SHA_A),expected)

if __name__=='__main__':unittest.main()
