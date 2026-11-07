import json
from contextlib import closing
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from migration.register_check import check
from migration.knowledge_inventory import inventory

class MigrationTests(unittest.TestCase):
    def test_capability_registry(self):
        status=check()
        self.assertGreaterEqual(status['mapped_capabilities'],14)
        self.assertEqual(status['status'],'PASS')
    def test_readonly_inventory_never_returns_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'catalogue.sqlite'
            with closing(sqlite3.connect(file)) as db, db:
                db.execute('CREATE TABLE artifacts (secret TEXT)')
                db.execute("INSERT INTO artifacts VALUES ('personal-sensitive-data')")
            before=file.read_bytes()
            report=inventory(file)
            self.assertEqual(report['table_rows'],{'artifacts':1})
            self.assertNotIn('personal-sensitive-data',json.dumps(report))
            self.assertEqual(file.read_bytes(),before)
            # Explicit unlink makes an unclosed SQLite handle fail on Windows.
            file.unlink()
            self.assertFalse(file.exists())
    def test_inventory_explicitly_closes_readonly_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'catalogue.sqlite'
            with closing(sqlite3.connect(file)) as db, db:
                db.execute('CREATE TABLE observations (id INTEGER)')
            closes=[]
            raw_connect=sqlite3.connect
            class TrackedConnection(sqlite3.Connection):
                def close(self):
                    closes.append(True)
                    return super().close()
            def tracked_connect(*args,**kwargs):
                kwargs['factory']=TrackedConnection
                return raw_connect(*args,**kwargs)
            with patch('migration.knowledge_inventory.sqlite3.connect',side_effect=tracked_connect):
                result=inventory(file)
            self.assertEqual(result['table_rows'],{'observations':0})
            self.assertEqual(closes,[True], 'Inventory must explicitly close its SQLite connection')
            file.unlink()
if __name__=='__main__':unittest.main()
