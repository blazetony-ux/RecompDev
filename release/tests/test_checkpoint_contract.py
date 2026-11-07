"""Source-only checks of isolated dev checkpoint plumbing; MSVC/PowerShell remains owner gate."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class OnePackageCheckpointTests(unittest.TestCase):
    def test_installer_changes_only_development_ref_after_full_tests(self):
        script = (ROOT/'Install-RecompDev-Release.ps1').read_text(encoding='utf8')
        for needle in ('WriteDevelopmentCheckpoint', 'GIT_INDEX_FILE', 'GIT_WORK_TREE',
                       "'read-tree'", "write-tree", "commit-tree", "update-ref",
                       'RECOMPDEV_DEV_MAIN_UNCHANGED=TRUE', "RECOMPDEV_PHASE=DEV_CHECKPOINT"):
            self.assertIn(needle, script)
        self.assertLess(script.index('Run $ctest @('), script.index('WriteDevelopmentCheckpoint\n', script.index("if($Mode -eq 'Validate')")))
        self.assertIn("$manifest.promotion_eligible -eq $true", script)

    def test_v04918_main_parent_requires_verified_infrastructure(self):
        script = (ROOT/'Install-RecompDev-Release.ps1').read_text(encoding='utf8')
        start = script.index("if($parentBranch -eq 'main'){")
        end = script.index('  Assert ($parentHash -match', start)
        branch = script[start:end]
        for check in ("$manifest.release_track -eq 'infrastructure-source'",
                      '$parentHash -eq [string]$manifest.baseline_commit',
                      '$oldHead -eq $parentHash'):
            self.assertIn(check, branch)
        self.assertIn("$parentBranch -eq 'main' -or $parentBranch -match", script)
        self.assertIn("'GIT_INDEX_FILE'", script)

    def test_isolated_git_index_preserves_checked_out_main(self):
        with tempfile.TemporaryDirectory(prefix='recompdev-single-package-') as tmp:
            repo = Path(tmp)/'repo'; repo.mkdir()
            def git(*args, env=None, cwd=repo):
                p=subprocess.run(['git','-C',str(cwd),*args],capture_output=True,text=True,env=env)
                if p.returncode: raise RuntimeError(f'{args}: {p.stderr}')
                return p.stdout.strip()
            git('init','-q')
            git('config','user.name','RecompDev Test')
            git('config','user.email','recompdev-test@example.invalid')
            (repo/'file.txt').write_text('v9')
            git('add','file.txt');git('commit','-qm','main baseline')
            main_sha = git('rev-parse','HEAD')
            git('branch','-m','main')
            git('branch','dev/v0.4.9.15')
            stage=Path(tmp)/'stage';stage.mkdir()
            (stage/'file.txt').write_text('v16')
            env={**os.environ,'GIT_INDEX_FILE':str(Path(tmp)/'independent.index'),
                 'GIT_WORK_TREE':str(stage)}
            git('read-tree','refs/heads/dev/v0.4.9.15',env=env)
            git('add','--','file.txt',env=env)
            tree=git('write-tree',env=env)
            parent=git('rev-parse','refs/heads/dev/v0.4.9.15')
            commit=git('commit-tree',tree,'-p',parent,'-m','candidate',env=env)
            git('update-ref','refs/heads/dev/v0.4.9.16',commit,'0'*40)
            self.assertEqual(main_sha,git('rev-parse','main'))
            self.assertEqual((repo/'file.txt').read_text(),'v9')
            self.assertEqual(git('show','dev/v0.4.9.16:file.txt'),'v16')

if __name__ == '__main__': unittest.main()
