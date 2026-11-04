"""Permanent regression for Windows-only SQLite file-locking test failures."""
import importlib.util
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('verify_sqlite_lifecycle',ROOT/'tools/Verify-SQLite-Lifecycle-v0444.py')
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class SqliteLifecycleTests(unittest.TestCase):
    def test_unsafe_connection_manager_is_rejected(self):
        s="import sqlite3\nwith sqlite3.connect('x.sqlite') as con: con.execute('select 1')\n"
        self.assertEqual(M.find_unsafe(s,'example.py'), [('example.py',2)])
    def test_both_safe_contexts_are_accepted(self):
        s="from contextlib import closing\nimport sqlite3\nwith closing(sqlite3.connect('x.sqlite')) as con, con: con.execute('select 1')\n"
        self.assertEqual(M.find_unsafe(s,'safe.py'),[])
    def test_every_shipped_python_file_has_no_unsafe_connection_managers(self):
        self.assertEqual(M.scan(ROOT),[])
    def test_mocked_windows_lock_detects_any_unclosed_cache_connection(self):
        # A tracked connection exposes the bug even on Linux (where unlinking
        # an open SQLite file would otherwise succeed).
        class Tracked(sqlite3.Connection):
            live=[]
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                self.closed_explicitly=False
                Tracked.live.append(self)
            def close(self):
                self.closed_explicitly=True
                return super().close()
        from unittest.mock import patch
        import hashlib,json
        from nativecore.verified_coverage_v0443 import VerifiedCoverageCache
        from test_continuous_recovery_v0435 import fixture
        original=sqlite3.connect
        def monitor(*args,**kwargs):
            kwargs['factory']=Tracked
            return original(*args,**kwargs)
        try:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)
                rom,export,overlay=fixture(root)
                cache_path=root/'verified-coverage-v0443.sqlite'
                with patch.object(sqlite3,'connect',monitor):
                    cache=VerifiedCoverageCache(cache_path,hashlib.sha256(rom.read_bytes()).hexdigest(),'synthetic')
                    cache.put(overlay,rom,6)
                    self.assertEqual(len(cache.load(rom)[0]),1)
                # Explicit closure required irrespective of reference lifetimes.
                self.assertFalse([c for c in Tracked.live if not c.closed_explicitly])
        finally:
            # Never leave leaked file handles behind even when asserting.
            for con in Tracked.live:
                if not con.closed_explicitly:con.close()

if __name__=='__main__':unittest.main()
