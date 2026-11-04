"""Fast documentation-governance gates; never compile or change source binaries."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from workspace import docs_governance, manager

ROOT = Path(__file__).resolve().parents[2]


class DocumentationGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='recompdev-doc-guard-')
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'RecompDev'
        self.source.mkdir()
        shutil.copytree(ROOT / 'docs', self.source / 'docs')
        (self.source / 'workspace').mkdir()
        shutil.copy2(ROOT / 'workspace/components.json', self.source / 'workspace/components.json')
        shutil.copy2(ROOT / 'CHANGELOG.md', self.source / 'CHANGELOG.md')
        shutil.copy2(ROOT / 'README.md', self.source / 'README.md')

    def test_complete_index_and_current_inventory(self):
        report = docs_governance.check(self.source)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['workspace_release'], 'workspace/v0.4.6')
        self.assertEqual(report['component_changelogs'], 17)

    def test_missing_handover_is_rejected(self):
        (self.source / 'docs/project/HANDOVER.md').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing authoritative documents'):
            docs_governance.check(self.source)

    def test_broken_link_is_rejected(self):
        path = self.source / 'docs/README.md'
        path.write_text(path.read_text(encoding='utf8') + '\n[broken](not-present-here.md)\n', encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'broken link'):
            docs_governance.check(self.source)

    def test_workspace_changelog_and_release_note_required(self):
        p = self.source / 'CHANGELOG.md'
        p.write_text(p.read_text(encoding='utf8').replace('workspace/v0.4.6', 'workspace/v0.4.4'), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'Workspace changelog'):
            docs_governance.check(self.source)

    def test_component_version_and_dated_changelog_required(self):
        p = self.source / 'docs/components/rd_cpu_z80/CHANGELOG.md'
        p.write_text(p.read_text(encoding='utf8').replace('## [0.2.0] -', '## [0.9.0] -'), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'Missing dated changelog'):
            docs_governance.check(self.source)

    def test_unrelated_component_version_change_rejected(self):
        before = json.loads((self.source / 'workspace/components.json').read_text())
        after = copy.deepcopy(before)
        after['components']['rd_cpu_z80']['version'] = '0.2.1'
        after['components']['rd_audio_wav']['version'] = '0.1.1'
        changes = {'workspace/components.json', 'harness/plugins/cpu_z80.cpp',
                   'docs/components/rd_cpu_z80/CHANGELOG.md'}
        with self.assertRaisesRegex(ValueError, 'Unrelated component'):
            manager.validate_component_diff('rd_cpu_z80', before, after, changes, source=self.source)

    def test_plugin_accept_must_change_its_own_changelog(self):
        before = json.loads((self.source / 'workspace/components.json').read_text())
        after = copy.deepcopy(before)
        after['components']['rd_cpu_z80']['version'] = '0.2.1'
        changes = {'workspace/components.json', 'harness/plugins/cpu_z80.cpp'}
        with self.assertRaisesRegex(ValueError, 'required component changelog'):
            manager.validate_component_diff('rd_cpu_z80', before, after, changes, source=self.source)

    def test_plugin_accept_with_meaningful_entry_is_permitted(self):
        before = json.loads((self.source / 'workspace/components.json').read_text())
        after = copy.deepcopy(before)
        after['components']['rd_cpu_z80']['version'] = '0.2.1'
        p = self.source / 'docs/components/rd_cpu_z80/CHANGELOG.md'
        p.write_text(p.read_text(encoding='utf8') + '''\n## [0.2.1] - 2026-11-04\n\n- **Changed:** Correct the documented synthetic Z80 decoder boundary and update test coverage for an explicit unsupported-opcode outcome.\n- **Validation:** Targeted unsupported_opcode_rejected, hybrid_main_parity and native_only_single_block regression gates passed.\n- **Compatibility:** No public ABI change; production native recovery continues to use the preserved legacy recovery engine, not this DLL.\n''', encoding='utf8')
        changes = {'workspace/components.json', 'harness/plugins/cpu_z80.cpp',
                   'docs/components/rd_cpu_z80/CHANGELOG.md'}
        manager.validate_component_diff('rd_cpu_z80', before, after, changes, source=self.source)

    def test_historical_files_were_not_moved_inside_protected_tree(self):
        self.assertTrue((ROOT / 'legacy/RecompDev-v0.4.0.45').exists())
        self.assertTrue((ROOT / 'baselines/ModularHarness-PoC-v0.3').exists())
        self.assertFalse((ROOT / 'RECOMPDEV-ARCHITECTURE-CONTRACT.md').exists())
        self.assertTrue((ROOT / 'docs/architecture/ARCHITECTURE-CONTRACT.md').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
