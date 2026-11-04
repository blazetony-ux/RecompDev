"""A new software version MUST NOT require a new versioned SQLite catalogue."""
import importlib.util
import os
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from nativecore.shared_catalogue import ensure_shared_catalogue, shared_path, legacy_sources

class SharedCatalogueTests(unittest.TestCase):
    def make_db(self, path, n):
        path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(path)) as con:
            for table in ('targets','graph_runs','graph_functions','discovery_sources','native_preparations_v0403'):
                con.execute('CREATE TABLE '+table+' (key INTEGER)')
            for i in range(n):
                con.execute('INSERT INTO discovery_sources (key) VALUES (?)',(i,))
            con.execute('INSERT INTO targets (key) VALUES (?)',(42,))
            con.commit()

    def test_bootstrap_once_then_share_across_versioned_installations(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'RECOMPDEV_DATA_DIR':str(Path(d)/'RecompDev-Data')},clear=False):
            p=Path(d);older=p/'RecompDev-v0.4.0.38';new=p/'RecompDev-v0.4.0.39';later=p/'RecompDev-v0.4.0.40';new.mkdir();later.mkdir()
            original=older/'catalogue.v0438-working.sqlite';self.make_db(original,3)
            self.make_db(new/'catalogue.sqlite',0)
            result=ensure_shared_catalogue(new)
            self.assertEqual(result['status'],'SQLITE_BACKUP_NEW_WORKING_DB')
            destination=Path(result['destination']);self.assertEqual(destination,p/'RecompDev-Data'/'catalogue.sqlite')
            self.assertEqual(Path(result['source']),original)
            with closing(sqlite3.connect(destination)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM discovery_sources').fetchone()[0],3)
                con.execute('INSERT INTO discovery_sources(key) VALUES (99)')
                con.commit()
            again=ensure_shared_catalogue(later)
            self.assertEqual(again['status'],'REUSED_SHARED_CATALOGUE')
            with closing(sqlite3.connect(destination)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM discovery_sources').fetchone()[0],4)
            self.assertTrue(original.is_file())
            with closing(sqlite3.connect(original)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM discovery_sources').fetchone()[0],3)

    def test_missing_previous_catalogue_uses_bundled_seed_once(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'RECOMPDEV_DATA_DIR':str(Path(d)/'data')},clear=False):
            root=Path(d)/'RecompDev-v0.4.0.39';root.mkdir()
            self.make_db(root/'catalogue.sqlite',1)
            self.assertEqual(ensure_shared_catalogue(root)['status'],'SQLITE_BACKUP_NEW_WORKING_DB')
            self.assertEqual(ensure_shared_catalogue(root)['status'],'REUSED_SHARED_CATALOGUE')

    def test_invalid_central_db_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'RECOMPDEV_DATA_DIR':str(Path(d)/'data')},clear=False):
            root=Path(d)/'RecompDev-v0.4.0.39';root.mkdir()
            self.make_db(root/'catalogue.sqlite',2)
            dest=shared_path(root);dest.parent.mkdir();dest.write_bytes(b'BROKEN_DB_NO_DELETE')
            with self.assertRaises(sqlite3.DatabaseError):ensure_shared_catalogue(root)
            self.assertEqual(dest.read_bytes(),b'BROKEN_DB_NO_DELETE')

    def test_explicit_override_and_catalogue_env(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'RecompDev-v0.4.0.39';root.mkdir()
            target=Path(d)/'shared'/'db.sqlite';one=Path(d)/'one.sqlite'
            with patch.dict(os.environ,{'RECOMPDEV_CATALOGUE':str(one)},clear=False):
                self.assertEqual(shared_path(root),one)
                self.assertEqual(shared_path(root,target),target)

    def test_campaign_prepares_shared_catalogue_before_dependency_check(self):
        root=Path(__file__).resolve().parents[1]
        s=(root/'tools'/'Run-SMS-Campaign-v0439.py').read_text(encoding='utf-8')
        self.assertIn('ensure_shared_catalogue(root)',s)
        self.assertLess(s.index('ensure_shared_catalogue(root)'),s.index('if not root.is_dir()'))
        self.assertNotIn('db = root / "catalogue.v0439-working.sqlite"',s)
        self.assertIn('from nativecore.campaign_compare_v0438 import compare_campaign',s)
        self.assertTrue((root/'baselines'/'sms-seven-v0436.json').is_file())

if __name__=='__main__':unittest.main()
