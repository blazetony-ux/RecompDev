"""Cross-workspace native evidence must be visible without inventing parity."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from discovery.store import SCHEMA as DISCOVERY_SCHEMA
from nativeprep.engine import SCHEMA as PREP_SCHEMA
from nativepilot.engine import SCHEMA as PILOT_SCHEMA
from workbench import data


class NativeProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'workbench.sqlite'
        self.con=sqlite3.connect(self.db)
        self.con.row_factory=sqlite3.Row
        self.con.executescript(DISCOVERY_SCHEMA+PREP_SCHEMA+PILOT_SCHEMA)
        self.sha='a'*64
        self.con.execute('INSERT INTO discovery_sources VALUES(?,?,?,?,?,?,?,?)',
            (self.sha,'C:/Roms/Game.sms',262144,'SHA256_COMPLETE','mastersystem','Test Cartridge','test','2026-10-31'))
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def test_unprepared_source_remains_visible_without_fabricated_coverage(self):
        progress=data(self.con,'native-progress',{})['games']
        self.assertEqual(len(progress),1)
        self.assertEqual(progress[0]['preparation_status'],'NOT_PREPARED')
        self.assertEqual(progress[0]['native_status'],'NOT_RUN')
        self.assertEqual(progress[0]['reference_parity'],'NOT_TESTED')

    def test_preparation_and_native_run_joined_by_source_sha(self):
        self.con.execute('INSERT INTO native_preparations_v0403 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
          (self.sha,'mastersystem-'+self.sha[:12],self.sha,'z80','mastersystem','CANDIDATES_RECOVERED_TRANSLATOR_NEEDED',48,0,'','', '2026-10-31'))
        self.con.execute('INSERT INTO native_pilots_v0404 VALUES(?,?,?,?,?,?,?,?)',
          (self.sha,'mastersystem-'+self.sha[:12],'NATIVE_STEP_BUDGET_REACHED',5075,500000,'STEP_BUDGET_REACHED','C:/Untrusted/result.json','2026-10-31'))
        self.con.execute('INSERT INTO native_bank_evidence_v0405 VALUES(?,?,?,?,?,?)',
          (self.sha,2,6,0x8000,'C:/Untrusted/bank.json','2026-10-31'))
        self.con.commit()
        entry=data(self.con,'native-progress',{})['games'][0]
        self.assertEqual(entry['candidate_count'],48)
        self.assertEqual(entry['translated_instructions'],5075)
        self.assertEqual(entry['native_steps'],500000)
        self.assertEqual(entry['bank_evidence_entries'],1)
        self.assertEqual(entry['reference_parity'],'NOT_TESTED')
        self.assertNotIn('report_available',entry)

    def test_missing_optional_tables_supported(self):
        self.con.execute('DROP TABLE native_pilots_v0404')
        self.con.execute('DROP TABLE native_preparations_v0403')
        self.con.commit()
        progress=data(self.con,'native-progress',{})['games']
        self.assertEqual(progress[0]['native_status'],'NOT_RUN')

if __name__=='__main__':unittest.main()
