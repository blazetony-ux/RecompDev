"""Main changelog immutable history and ordering regressions."""
from pathlib import Path
import unittest
from workspace.docs_governance import check_workspace_changelog

ROOT=Path(__file__).resolve().parents[2]

class ChangelogOrderTests(unittest.TestCase):
    def test_current_main_changelog_passes(self):
        check_workspace_changelog((ROOT/'CHANGELOG.md').read_text(encoding='utf8'),'workspace/v0.4.9.8')

    def test_title_must_be_first(self):
        with self.assertRaisesRegex(ValueError,'begin'):
            check_workspace_changelog('## [workspace/v0.4.9.6] - 2026-11-05\n# RecompDev workspace changelog\n', 'workspace/v0.4.9.6')

    def test_duplicate_release_rejected(self):
        s='# RecompDev workspace changelog\n\n## [workspace/v0.4.9.6] - 2026-11-05\n## [workspace/v0.4.9.6] - 2026-11-05\n'
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            check_workspace_changelog(s,'workspace/v0.4.9.6')

    def test_out_of_order_release_rejected(self):
        s='# RecompDev workspace changelog\n\n## [workspace/v0.4.9.6] - 2026-11-05\n## [workspace/v0.4.5] - 2026-11-04\n## [workspace/v0.4.8] - 2026-11-04\n'
        with self.assertRaisesRegex(ValueError,'newest-first'):
            check_workspace_changelog(s,'workspace/v0.4.9.6')

if __name__ == '__main__':unittest.main()
