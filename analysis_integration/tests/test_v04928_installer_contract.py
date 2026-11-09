"""Static policy checks, NOT a substitute for Windows PowerShell execution."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
S = (ROOT / 'Install-RecompDev-Release.ps1').read_text(encoding='utf8')
L = (ROOT / 'analysis_integration' / 'live_session.py').read_text(encoding='utf8')


class InstallerPolicy(unittest.TestCase):
    def test_install_only_remote_publication(self):
        self.assertIn('[switch]$PublishOrigin', S)
        self.assertIn("Assert (-not $PublishOrigin -or $Mode -eq 'Install')", S)
        self.assertIn("if($Mode -eq 'Install' -and $releaseOk)", S)
        self.assertIn("'push','--atomic','origin'", S)
        self.assertIn("'HEAD:refs/heads/main'", S)
        self.assertIn("'refs/tags/'+$tag+':refs/tags/'+$tag", S)
        self.assertNotIn("'--force'", S)

    def test_restore_after_local_verified_release(self):
        phase = S.index('RECOMPDEV_PHASE=GENERATED_SOURCE_RESTORE_AFTER_INSTALL')
        self.assertGreater(phase, S.index('RECOMPDEV_RELEASE_RESULT=INFRASTRUCTURE_SOURCE_INSTALLED'))
        self.assertGreater(phase, S.index('RECOMPDEV_RELEASE_RESULT=INSTALLED'))
        self.assertIn('restore-all --home $generatedHome', S)
        self.assertIn('setup --home $generatedHome --repository $defaultShared', S)
        self.assertIn('PENDING_RETRY_LOCAL_RELEASE_UNCHANGED', S)

    def test_no_qualified_runtime_shortcut(self):
        self.assertIn("$manifest.promotion_eligible -eq $true", S)
        self.assertIn("$manifest.promotion_scope -eq 'git-main-only-no-runtime'", S)
        self.assertIn("RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED=TRUE", S)

    def test_live_play_checkpoint_every_ack_and_background(self):
        self.assertIn('source_sync.AutoPublisher(home)', L)
        self.assertIn('source_publisher.queued(sha_rom,report[\'generated_source_commit\'])', L)
        self.assertNotIn('if activated_count%4==0', L)
        self.assertIn('source_publisher.finish()', L)


if __name__ == '__main__': unittest.main()
