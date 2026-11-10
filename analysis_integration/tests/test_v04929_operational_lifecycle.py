"""v29 real-Git retry and lifecycle acceptance; no public GitHub network."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from analysis_integration import generated_source_sync as sync

SHA='c'*64

def git(path,*args):
    p=subprocess.run(['git','-C',str(path),*args],capture_output=True,text=True)
    if p.returncode:raise AssertionError((args,p.stderr))
    return p.stdout.strip()

class OperationalGit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home';self.remote=self.root/'remote.git';self.shared=self.root/'shared'
        git(self.root,'init','--bare',str(self.remote));git(self.root,'clone',str(self.remote),str(self.shared))
        git(self.shared,'checkout','-b','main')
        git(self.shared,'-c','user.name=Fixture','-c','user.email=fixture@test.invalid','commit','--allow-empty','-m','main')
        git(self.shared,'push','origin','main');sync.setup(self.home,self.shared)
        self.source=self.home/'gs'/SHA;self.source.mkdir(parents=True)
        git(self.source,'init','-b','main')
        path=self.source/'m'/('1'*64)/'s';path.mkdir(parents=True)
        (path/'translated.cpp').write_text('// native\n')
        (self.source/'compatibility.json').write_text(json.dumps({'rom_sha256':SHA})+'\n')
        git(self.source,'add','.');git(self.source,'-c','user.name=Fixture','-c','user.email=fixture@test.invalid','commit','-m','native')
        self.commit=git(self.source,'rev-parse','HEAD')

    def test_automatic_retry_after_offline_period(self):
        sync.mark_pending(self.home,SHA,self.commit)
        git(self.shared,'remote','set-url','origin',str(self.root/'unavailable.git'))
        with self.assertRaises(sync.SyncError):sync.retry_pending(self.home)
        self.assertEqual(sync.pending_items(self.home)[SHA],self.commit)
        git(self.shared,'remote','set-url','origin',str(self.remote))
        result=sync.retry_pending(self.home)
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(result['retried'],1)
        self.assertEqual(sync.pending_items(self.home),{})
        self.assertEqual(sync.retry_pending(self.home)['status'],'UP_TO_DATE')

    def test_retries_during_existing_game_session_without_new_translation(self):
        sync.mark_pending(self.home,SHA,self.commit)
        git(self.shared,'remote','set-url','origin',str(self.root/'unavailable.git'))
        attempts=[];original=sync.retry_pending;finished=threading.Event()
        def publish(home):
            attempts.append(1)
            if len(attempts)==1:raise sync.SyncError('OFFLINE')
            git(self.shared,'remote','set-url','origin',str(self.remote))
            result=original(home)
            finished.set()
            return result
        with patch.object(sync,'retry_pending',side_effect=publish):
            worker=sync.AutoPublisher(self.home,retry_delays=(0.02,0.04))
            self.assertTrue(finished.wait(10),'Automatic retry did not publish')
            worker.finish()
        self.assertGreaterEqual(len(attempts),2)
        self.assertFalse(sync.pending_items(self.home))

    def test_new_session_retries_prior_session_queue_without_any_new_module(self):
        sync.mark_pending(self.home,SHA,self.commit)
        git(self.shared,'remote','set-url','origin',str(self.root/'unavailable.git'))
        first=sync.AutoPublisher(self.home,retry_delays=(0.1,0.1))
        time.sleep(0.2)
        first.finish()
        self.assertEqual(sync.pending_items(self.home)[SHA],self.commit)
        git(self.shared,'remote','set-url','origin',str(self.remote))
        second=sync.AutoPublisher(self.home,retry_delays=(0.1,0.1))
        for _ in range(150):
            if not sync.pending_items(self.home):break
            time.sleep(0.05)
        second.finish()
        self.assertEqual(sync.pending_items(self.home),{})
        self.assertEqual(git(self.shared,'rev-parse','HEAD'),git(self.shared,'ls-remote','origin','refs/heads/main').split()[0])

    def test_rejected_or_corrupt_pending_record_is_not_erased(self):
        sync.mark_pending(self.home,SHA,self.commit)
        p=sync.pending_path(self.home,SHA)
        p.write_text('{"rom_sha256":"wrong","source_commit":"broken"}')
        with self.assertRaisesRegex(sync.SyncError,'SYNC_PENDING_RECORD_INVALID'):
            sync.pending_items(self.home)
        self.assertTrue(p.is_file())
        self.assertEqual(git(self.source,'rev-parse','HEAD'),self.commit)

    def test_cli_reports_pending_state_and_exact_source_after_retry(self):
        sync.mark_pending(self.home,SHA,self.commit)
        r=subprocess.run([sys.executable,'-B',str(ROOT/'analysis_integration/generated_source_sync.py'),
                          'status','--home',str(self.home)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0)
        self.assertIn('"pending": 1',r.stdout)
        sync.retry_pending(self.home)
        restored=self.root/'restore'
        sync.setup(restored,self.shared)
        self.assertEqual(sync.restore_all(restored)['restored'],1)
        self.assertEqual(git(restored/'gs'/SHA,'rev-parse','HEAD'),self.commit)

if __name__=='__main__':unittest.main()
