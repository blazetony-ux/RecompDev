#!/usr/bin/env python3
"""Real v0445 discovery/native-preparation/recovery adapters, provenance and parity."""
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from modular import controller
from modular.plugins import legacy
from migration import controller as preservation

ROM = ROOT/'harness/examples/recomp-pcode/synthetic.sms'
EXPORT = ROOT/'harness/examples/recomp-pcode/function-export.json'

class TestRealLegacyServices(unittest.TestCase):
    def test_registry_points_to_original_services(self):
        found=legacy.registry()
        self.assertEqual(set(found),{'legacy.discovery','legacy.preparation','legacy.recovery','legacy.sms-campaign'})
        for key in found:
            self.assertIn('legacy/RecompDev-v0.4.0.45',found[key]['source'])
            self.assertTrue((ROOT/found[key]['source']).is_file())

    def test_real_original_discovery_parity(self):
        """Compare actual v0445 database rows, not mocked response objects."""
        with tempfile.TemporaryDirectory(prefix='rd041-parity-') as tmp:
            result=controller.compare_discovery(ROM, Path(tmp)/'side-by-side',budget=10)
            self.assertEqual(result['status'],'PASS',result)
            self.assertTrue(all(result['row_level_equivalence'].values()))
            self.assertTrue(result['source_catalogue_unchanged'])
            self.assertTrue(result['original_rom_unchanged'])

    def test_real_native_preparation_reports_missing_ghidra(self):
        with tempfile.TemporaryDirectory(prefix='rd041-prep-') as tmp:
            output=Path(tmp)/'run'
            result=controller.run_rom(ROM,output,stage='prepare',budget=10)
            self.assertIn(result['status'],('PREPARATION_BLOCKED','PREPARATION_COMPLETE'))
            self.assertEqual(result['system'],'mastersystem')
            self.assertEqual(result['cpu'],'z80')
            self.assertFalse(result['production_catalogue_mutated'])
            self.assertTrue(output.joinpath('discovery/discovery-report.json').exists())
            self.assertTrue(output.joinpath('preparation/preparation-report.json').exists())
            self.assertTrue(output.joinpath('controller-report.json').exists())
            self.assertTrue(all(x['preserved_production_implementation'] for x in result['services']))

    def test_no_reuse_of_evidence_folder(self):
        with tempfile.TemporaryDirectory(prefix='rd041-overwrite-') as tmp:
            output=Path(tmp)/'run'
            first=controller.run_rom(ROM,output,stage='discover',budget=5)
            self.assertEqual(first['status'],'DISCOVERY_COMPLETE')
            with self.assertRaises(ValueError):
                controller.run_rom(ROM,output,stage='discover',budget=5)

    def test_bad_plugin_registration_is_rejected(self):
        with self.assertRaises(legacy.PipelineError):
            legacy.invoke('arbitrary',[],ROOT/'ignore-unknown')

    def test_readonly_external_catalogue_snapshotted(self):
        with tempfile.TemporaryDirectory(prefix='rd041-catalogue-') as tmp:
            src=Path(tmp)/'source.sqlite'
            preservation.catalogue_snapshot(controller.DEFAULT_DB,src)
            start=preservation.sha(src)
            result=controller.run_rom(ROM,Path(tmp)/'isolated',stage='discover',database=src,budget=5)
            self.assertEqual(result['status'],'DISCOVERY_COMPLETE')
            self.assertEqual(start,preservation.sha(src))
            self.assertTrue(result['source_image_unchanged'])

    def test_real_recovery_invoked_with_authenticated_pcode(self):
        """Actual legacy C++ compilation path; getting blocked is a valid diagnosis."""
        with tempfile.TemporaryDirectory(prefix='rd041-recovery-') as tmp:
            output=Path(tmp)/'run'
            result=controller.run_rom(ROM,output,stage='recover',export=str(EXPORT),
                                      budget=10,steps=50,frames=1,recoveries=0,timeout=150)
            self.assertEqual(result['authenticated_export']['status'],'PASS')
            self.assertEqual(result['authenticated_export']['physically_attested_instructions'],6)
            self.assertEqual(result['services'][-1]['plugin'],'legacy.recovery')
            self.assertTrue(output.joinpath('recovery/continuous-recovery-report.json').exists())
            details=json.loads(output.joinpath('recovery/continuous-recovery-report.json').read_text())
            self.assertGreaterEqual(len(details['attempts']),1)
            self.assertTrue(details['attempts'][0]['translated_instructions']>0)
            self.assertEqual(details['gameplay'],'NOT_ESTABLISHED')
            self.assertTrue(result['source_image_unchanged'])
            self.assertFalse(result['production_catalogue_mutated'])

    def test_original_seven_game_campaign_dispatch(self):
        # No commercial ROMs are bundled. Prove the original orchestrator runs,
        # records all seven missing inputs honestly, and never mutates catalogue.
        with tempfile.TemporaryDirectory(prefix='rd041-campaign-') as tmp:
            root=Path(tmp)
            romdir=root/'empty-rom-folder'
            romdir.mkdir()
            result=controller.run_campaign(romdir,root/'run',frames=1,steps=100,
                                           recoveries=0,timeout=60)
            self.assertEqual(result['status'],'NO_MATCHING_ROMS',result)
            self.assertEqual(len(result['game_statuses']),7)
            self.assertTrue(all(s=='ROM_NOT_FOUND' for s in result['game_statuses'].values()))
            self.assertFalse(result['production_catalogue_mutated'])

    def test_full_source_preservation_gate(self):
        self.assertEqual(preservation.verify()['unchanged_original_files'],642)

if __name__=='__main__':
    unittest.main(verbosity=2)
