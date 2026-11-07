"""Source-only release contract checks; not a replacement for Windows PowerShell acceptance."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

class ReleaseProtocolTests(unittest.TestCase):
    def test_one_permanent_script_and_git_contract(self):
        p = ROOT / 'Install-RecompDev-Release.ps1'
        script = p.read_text(encoding='utf8')
        for token in ('ExpectedSha256', 'release-manifest.json', 'GitBlobToFile',
                      'RECOMPDEV_RELEASE_MODE', 'Validate', 'Install',
                      'legacy/', 'baselines/', 'ctest', 'git-head.zip',
                      'RECOMPDEV_ROLLBACK', 'RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED'):
            self.assertIn(token, script)
        self.assertNotIn('RECOMPDEV_UNIVERSAL_PROGRESS=', script)
        self.assertNotIn('UEsDB', script)  # No embedded per-release ZIP

    def test_release_path_policy_allows_markdown(self):
        # Windows regression: a Sega .md image must not cause all Markdown
        # documentation to be rejected by filename alone.
        script = (ROOT/'Install-RecompDev-Release.ps1').read_text(encoding='utf8')
        path_policy = script.split('function ValidPath', 1)[1].split('function GitBlobToFile', 1)[0]
        self.assertNotIn('|md|', path_policy)
        self.assertIn('legacy/', path_policy)
        self.assertIn('baselines/', path_policy)
        self.assertIn('rom|sms|iso|img|bin', path_policy)
        self.assertIn("if($rel -match '\\.md$')", script)
        self.assertIn('Markdown source is not UTF-8 text', script)

    def test_git_archived_stage_restores_sha_verified_ignored_history(self):
        # Git does not track one protected evidence/baselines member, even though
        # the authoritative 642-file historical manifest still requires it.
        script = (ROOT/'Install-RecompDev-Release.ps1').read_text(encoding='utf8')
        self.assertIn('function RestoreManifestDeclaredHistoricalFiles', script)
        self.assertIn('RestoreManifestDeclaredHistoricalFiles\n', script)
        self.assertIn("RECOMPDEV_PHASE=RESTORE_MANIFEST_DECLARED_HISTORY", script)
        self.assertIn('migration\\source-integrity-manifest.json', script)
        self.assertIn('Historical source SHA-256 mismatch:', script)
        self.assertIn('Historical staged SHA-256 mismatch:', script)
        self.assertIn('$stageMatches=', script)
        self.assertIn('Historical source byte count mismatch:', script)
        self.assertIn('RECOMPDEV_STAGED_HISTORICAL_RESTORED=', script)
        self.assertIn("$group.root", script)
        self.assertNotIn('Remove-Item -LiteralPath $originalFile', script)

    def test_installable_scope_does_not_claim_translation(self):
        text=(ROOT/'docs/releases/v0.4.9.8.md').read_text()
        self.assertIn('INSTALLABLE PACKAGE', text)
        self.assertIn('v0.4.9.7 was not installed', text)
        self.assertIn('P-code', text)
        self.assertIn('Shinobi', text)
        self.assertIn('deferred', text)
        self.assertIn('owner installation pending', text)

    def test_controller_lockfile_key_is_consistent(self):
        script=(ROOT/'Install-RecompDev-Release.ps1').read_text()
        self.assertIn("$name -eq 'controller'", script)
        self.assertIn("$module.component -eq 'controller'", script)
        self.assertIn("$state.active.PSObject.Properties['controller']", script)
        self.assertIn('Installed component hash mismatch',script)
        self.assertIn('Release Git tag verification failed',script)
        self.assertIn('Git index rollback failed',script)
        self.assertNotIn("$module.component -eq 'RecompDev'",script)

    def test_installer_registered_without_runtime_plugin_claim(self):
        doc=json.loads((ROOT/'workspace/components.json').read_text())
        self.assertRegex(doc['workspace_release'], r'^v0\.4\.9\.(?:[8-9]|[1-9]\d+)$')
        self.assertEqual(doc['components']['release_installer']['scope'],'workspace')
        self.assertEqual(doc['components']['release_installer']['version'],'1.2.0')

    def test_baseline_and_documented_first_bootstrap(self):
        p=(ROOT/'docs/development/RELEASE-PROCESS.md').read_text()
        self.assertIn('7243e62851684477764117398b48ee335673eac2', p)
        self.assertIn('one-time', p.lower())
        self.assertIn('Downloads', p)
        self.assertIn('workspace/v0.4.9.6', p)

if __name__ == '__main__':
    unittest.main()
