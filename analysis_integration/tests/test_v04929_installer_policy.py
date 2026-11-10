"""Source-release installer must stage, verify and never silently activate."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
INSTALL=(ROOT/'Install-RecompDev-Release.ps1').read_text(encoding='utf-8')
SYNC=(ROOT/'analysis_integration/generated_source_sync.py').read_text(encoding='utf-8')

class InstallerRuntimeAndSyncPolicy(unittest.TestCase):
    def test_runtime_stage_after_build_inventory_before_success(self):
        self.assertLess(INSTALL.index('RECOMPDEV_BINARY_HASHES='), INSTALL.index('RECOMPDEV_RUNTIME_IMAGE_STATUS=VERIFIED_NOT_ACTIVATED'))
        self.assertLess(INSTALL.index('RECOMPDEV_RUNTIME_IMAGE_STATUS=VERIFIED_NOT_ACTIVATED'), INSTALL.index('RECOMPDEV_TESTS=PASS'))
        self.assertIn("'verify','--destination',$stageImage,'--inventory',$inventoryFile",INSTALL)
        self.assertIn("$manifest.promotion_scope -eq 'git-main-only-no-runtime'",INSTALL)
        self.assertIn('RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED=TRUE',INSTALL)
    def test_published_only_after_queue_is_empty(self):
        self.assertIn('RECOMPDEV_GENERATED_SOURCE_PENDING=$pendingCount',INSTALL)
        self.assertIn('if($publishExit -ne 0 -or $pendingCount -ne 0)',INSTALL)
        self.assertLess(INSTALL.index('$publishExit=$LASTEXITCODE'), INSTALL.index('RECOMPDEV_GENERATED_SOURCE_PUBLICATION=VERIFIED'))
        self.assertNotIn("'push','--force'",INSTALL)
    def test_restart_and_periodic_retry_are_not_guest_gates(self):
        self.assertIn('self.wake.wait(timeout=delay)', SYNC)
        self.assertIn('result = retry_pending(self.home)', SYNC)
        self.assertIn("print('RECOMPDEV_GENERATED_SYNC_FINAL='", SYNC)
        self.assertIn("choices=('setup', 'publish', 'restore-all', 'retry-pending', 'status')", SYNC)

if __name__=='__main__':unittest.main()
