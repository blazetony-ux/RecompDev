#!/usr/bin/env python3
"""Executable non-destructive migration gates, run individually by CTest."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from migration import controller


class TestPreservation(unittest.TestCase):
    def test_all_original_files_identical(self):
        result = controller.verify()
        self.assertEqual(result['unchanged_original_files'], 642)
        self.assertEqual(result['legacy_catalogue_tables'], 14)

    def test_registry_covers_main_subsystems_and_blockers(self):
        doc = controller.status()
        self.assertGreaterEqual(len(doc['capabilities']), 7)
        self.assertIn('BLOCKED', doc['gates']['G6-release'])
        self.assertIn('MISSING', doc['external_evidence']['status'])

    def test_direct_production_runtime_not_legacy_vendor_copy(self):
        cmake = (ROOT / 'harness/CMakeLists.txt').read_text()
        self.assertIn('add_library(rd_sms_native_runtime SHARED ../runtime_sms/src/runtime.cpp)', cmake)
        self.assertNotIn('target_sources(rd_machine_sms PRIVATE ../legacy/', cmake)
        self.assertNotIn('target_include_directories(rd_runtime_host PRIVATE ../runtime_host/include ../legacy/', cmake)
        translator=(ROOT / 'translation_pcode/src/translator.cpp').read_text()
        self.assertIn('ACTIVE_SMS_RUNTIME_SOURCE_MISSING',translator)
        self.assertNotIn('legacy/"RecompDev-v0.4.0.45"',translator)
        self.assertNotIn('nativepilot/z80_cycles.hpp', translator)
        gen=(ROOT / 'harness/tools/build_pcode_plugin.py').read_text()
        self.assertIn('z80_cycles.hpp', gen)


class TestProductionBridge(unittest.TestCase):
    def test_genuine_production_pcode_verifier(self):
        sample = ROOT / 'harness/examples/recomp-pcode'
        result = controller.pcode_verify(sample / 'synthetic.sms', sample / 'function-export.json',
                                          [sample / 'bank3-export.json'])
        self.assertEqual(result['status'], 'PASS')
        self.assertGreaterEqual(result['physically_attested_instructions'], 8)
        self.assertFalse(result['native_gameplay_qualification'])

    def test_forged_export_rejected(self):
        sample = ROOT / 'harness/examples/recomp-pcode'
        doc = json.loads((sample / 'function-export.json').read_text())
        doc['source_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as d:
            forged = Path(d) / 'forged.json'
            forged.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                controller.pcode_verify(sample / 'synthetic.sms', forged, [])

    def test_external_service_is_read_only(self):
        request = {'api': 'recompdev-service-jsonl-v1', 'operation': 'ping'}
        illegal = {'api': 'recompdev-service-jsonl-v1', 'operation': 'discovery.write'}
        worker = ROOT / 'services/legacy_service.py'
        proc = subprocess.run([sys.executable, str(worker)], input=json.dumps(request)+'\n'+json.dumps(illegal)+'\n',
                              capture_output=True, text=True, cwd=ROOT, check=True)
        responses = [json.loads(x) for x in proc.stdout.splitlines()]
        self.assertTrue(responses[0]['ok'])
        self.assertFalse(responses[1]['ok'])
        self.assertEqual(responses[0]['result']['mutations'], 'none')

    def test_live_legacy_discovery_schema_service(self):
        worker = ROOT / 'services/legacy_service.py'
        request = {'api': 'recompdev-service-jsonl-v1', 'operation': 'discovery.schema'}
        proc = subprocess.run([sys.executable, str(worker)], input=json.dumps(request)+'\n',
                              capture_output=True, text=True, cwd=ROOT, check=True)
        response = json.loads(proc.stdout)
        self.assertTrue(response['ok'])
        self.assertIn('discovery_sources', response['result']['tables'])


class TestCatalogueSafety(unittest.TestCase):
    def test_read_only_copy_and_exact_table_counts(self):
        source = controller.LEGACY / 'catalogue.sqlite'
        digest = controller.sha(source)
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'migration-sidecar.sqlite'
            result = controller.catalogue_snapshot(source, dest)
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(controller.sha(source), digest)
            self.assertEqual(controller.catalogue_inspect(source)['tables'],
                             controller.catalogue_inspect(dest)['tables'])
            with self.assertRaises(ValueError):
                controller.catalogue_snapshot(source, dest)

    def test_missing_external_evidence_never_synthesized(self):
        self.assertEqual(controller.status()['external_evidence']['status'],
                         'MISSING_FROM_UPLOADED_ARCHIVE')

    def test_inventory_does_not_modify_external_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'owner'
            root.mkdir()
            (root / 'evidence.txt').write_text('evidence')
            out = Path(tmp) / 'inventory.json'
            before = controller.sha(root / 'evidence.txt')
            report = controller.inventory_external(root, out)
            self.assertEqual(report['files'], 1)
            self.assertEqual(before, controller.sha(root / 'evidence.txt'))
            with self.assertRaises(ValueError):
                controller.inventory_external(root, out)


class TestOriginalRegressions(unittest.TestCase):
    def test_original_z80_and_cross_isa(self):
        outcome = controller.run_legacy_tests(['test_z80_timing_v0433.py',
                                               'test_cross_isa_recovery_v0430.py'])
        self.assertEqual(outcome['status'], 'PASS')
        self.assertEqual(len(outcome['tests']), 2)
        self.assertTrue(all(x['passed'] for x in outcome['tests']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
