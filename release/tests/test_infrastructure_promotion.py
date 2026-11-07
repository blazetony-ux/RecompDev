"""Infrastructure source promotion is intentionally not a game runtime release."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class InfrastructurePolicyTests(unittest.TestCase):
    def test_installer_keeps_source_promotion_independent(self):
        script=(ROOT/'Install-RecompDev-Release.ps1').read_text()
        start=script.index("}elseif($manifest.release_track -eq 'infrastructure-source'){")
        end=script.index("  }else{\n    Write-Host 'RECOMPDEV_PHASE=ACTIVATE_AFTER_TESTS'",start)
        branch=script[start:end]
        for marker in ('INFRASTRUCTURE_SOURCE_PROMOTION', 'git', 'CopySourceToCheckout',
                       'commit', 'tag', 'gitBundle', 'RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED=TRUE',
                       'RECOMPDEV_RUNTIME_QUALIFIED=FALSE'):
            self.assertIn(marker,branch)
        for forbidden in ('Copy-Item -LiteralPath $store -Destination $target', '$runtimeTouched=$true', 'active-components.next.json'):
            self.assertNotIn(forbidden,branch)
        self.assertIn("$manifest.release_track -eq 'infrastructure-source'",script)
        self.assertIn("$manifest.gameplay_qualified -eq $false",script)
        self.assertIn("$manifest.promotion_scope -eq 'git-main-only-no-runtime'",script)

    def test_contract_preserves_gameplay_gates(self):
        doc=(ROOT/'docs/project/DEVELOPMENT-CONTRACT.md').read_text(encoding='utf8')
        release=(ROOT/'docs/releases/v0.4.9.17.md').read_text(encoding='utf8')
        for token in ('1,800','Shinobi','runtime','infrastructure'):
            self.assertIn(token.lower(),doc.lower())
            self.assertIn(token.lower(),release.lower())

if __name__=='__main__':unittest.main()
