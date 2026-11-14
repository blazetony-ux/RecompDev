#!/usr/bin/env python3
"""Local bare-Git acceptance: ancestor-only, no forced or unrelated pushes."""
import subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from release.origin_publication import audit,PublicationFailure

class Publication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='rd-v37-git-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.origin=self.root/'origin.git'
        self.repo=self.root/'repo'
        self.git_run(None,'git','init','--bare',str(self.origin))
        self.git_run(None,'git','init','-b','main',str(self.repo))
        for key,value in (('user.name','RecompDev Fixture'),('user.email','fixture@localhost')):
            self.git_run(self.repo,'git','config',key,value)
        self.git_run(self.repo,'git','remote','add','origin',str(self.origin))
        self.commit(self.repo,'initial')
        self.git_run(self.repo,'git','push','origin','main')
    def git_run(self,repo,*args):
        p=subprocess.run(list(args),cwd=str(repo) if repo is not None else None,capture_output=True,text=True,timeout=30)
        if p.returncode:raise AssertionError(' '.join(args)+'\n'+p.stdout+'\n'+p.stderr)
        return p.stdout
    def commit(self,repo,msg):
        name=repo/'readme.txt'
        name.write_text((name.read_text() if name.exists() else '')+msg+'\n')
        self.git_run(repo,'git','add','readme.txt')
        self.git_run(repo,'git','commit','-m',msg)
    def test_fast_forward_and_tag_verified(self):
        self.commit(self.repo,'v37')
        self.git_run(self.repo,'git','tag','-a','workspace/v0.4.9.37','-m','v37')
        a=audit(self.repo,'workspace/v0.4.9.37','preflight')
        self.assertEqual(a['status'],'SAFE_FAST_FORWARD')
        self.assertFalse(a['push_executed_by_helper'])
        self.git_run(self.repo,'git','push','--atomic','origin','HEAD:refs/heads/main',
                 'refs/tags/workspace/v0.4.9.37:refs/tags/workspace/v0.4.9.37')
        self.assertEqual(audit(self.repo,'workspace/v0.4.9.37','verify')['status'],'VERIFIED')
    def test_remote_divergence_rejected_before_push(self):
        self.commit(self.repo,'local-change')
        self.git_run(self.repo,'git','tag','-a','workspace/v0.4.9.37','-m','v37')
        other=self.root/'other';self.git_run(None,'git','clone','-b','main',str(self.origin),str(other))
        for key,value in (('user.name','Other'),('user.email','other@localhost')):
            self.git_run(other,'git','config',key,value)
        self.commit(other,'remote-change');self.git_run(other,'git','push','origin','main')
        with self.assertRaisesRegex(PublicationFailure,'NOT_ANCESTOR'):
            audit(self.repo,'workspace/v0.4.9.37','preflight')
    def test_conflicting_remote_tag_rejected(self):
        self.git_run(self.repo,'git','tag','-a','workspace/v0.4.9.37','-m','initial-release')
        self.git_run(self.repo,'git','push','origin','workspace/v0.4.9.37')
        self.commit(self.repo,'v37-new-commit')
        self.git_run(self.repo,'git','tag','-f','-a','workspace/v0.4.9.37','-m','replacement')
        with self.assertRaisesRegex(PublicationFailure,'TAG_ALREADY_EXISTS'):
            audit(self.repo,'workspace/v0.4.9.37','preflight')
    def test_installer_policy_remains_opt_in_and_atomic(self):
        text=(ROOT/'Install-RecompDev-Release.ps1').read_text(encoding='utf8')
        self.assertIn('[switch]$PublishOrigin',text)
        self.assertIn("Assert (-not $PublishOrigin -or $Mode -eq 'Install')",text)
        self.assertIn("'push','--atomic','origin'",text)
        self.assertIn('Origin fast-forward preflight rejected publication',text)
        self.assertIn('Origin hash verification rejected publication',text)
        self.assertIn('RECOMPDEV_ORIGIN_EVIDENCE=',text)
        self.assertNotIn("'--force'",text)
if __name__=='__main__':unittest.main(verbosity=2)
