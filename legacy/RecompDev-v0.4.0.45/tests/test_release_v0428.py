"""v0.4.0.28 regression: Windows path normalization, SQL handle closure and cache isolation."""
import ast
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from tooling.release_contract import version
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class WindowsPortabilityContracts(unittest.TestCase):
    def test_versioned_entrypoints_and_previous_catalogue(self):
        self.assertIn('VERSION '+version(ROOT),(ROOT/'nativepilot/CMakeLists.txt').read_text())
        self.assertIn('v'+version(ROOT),(ROOT/'static/tooling.html').read_text())
        script=(ROOT/'Run-Workbench.ps1').read_text()
        self.assertIn('catalogue.v0432-working.sqlite',script)
        self.assertIn(r'RecompDev-v0.4.0.27\catalogue.v0427-working.sqlite',script)
        self.assertIn('FILE_SHA256_v0428.json',(ROOT/'Verify-v0428.ps1').read_text())
        self.assertIn('BUILD_VALIDATION_v0435.json',(ROOT/'workbench.py').read_text())
        self.assertIn("'release':'"+version(ROOT)+"'",(ROOT/'workbench.py').read_text())

    def test_sqlite_context_manager_does_not_implicitly_close(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'sqlite-lifetime.db'
            with closing(sqlite3.connect(p)) as conn:
                with conn:
                    conn.execute('CREATE TABLE t(x INT)')
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM t').fetchone()[0],0)
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute('SELECT COUNT(*) FROM t')
            p.unlink()  # catches WinError 32 from leaked conn on Windows

    def test_no_raw_sqlite_connection_context_managers_in_fixture_suite(self):
        # `with sqlite3.connect()` handles transactions but not Windows file
        # descriptor closure. Reject this pattern in all regression fixtures.
        for source in sorted((ROOT/'tests').glob('test_*.py')):
            tree=ast.parse(source.read_text(encoding='utf-8'),filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node,(ast.With,ast.AsyncWith)):
                    for item in node.items:
                        expr=item.context_expr
                        if not isinstance(expr,ast.Call):continue
                        f=expr.func
                        if (isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name)
                            and f.value.id in ('sqlite3','store') and f.attr=='connect'):
                            self.fail(f'{source.name}:{node.lineno} uses sqlite3 connection without explicit close')

    def test_cache_fixture_no_longer_conflates_compiler_with_authenticity(self):
        t=(ROOT/'tests/test_blockers_v032.py').read_text()
        self.assertIn("patch('recovery.pipeline.find_cpp_compiler'",t)
        self.assertIn("'COMPILER_NOT_FOUND'",t)
        self.assertIn("'LOWERED_RAW_PCODE_UNVERIFIED'",t)
        self.assertIn('str(original)',t)

    def test_compiled_native_acceptance_is_still_mandatory(self):
        gate=(ROOT/'tooling/gates_v0428.py').read_text()
        self.assertIn("'test_null_backends_v0425.py'",gate)
        self.assertIn('p.returncode',gate)
        self.assertIn("'skipped='",gate)
        from tooling.gates_v0428 import run
        result=run(run_tests=False)
        self.assertFalse(result['native_qualified'])
        self.assertEqual(result['milestones']['SHINOBI_GAMEPLAY'],'NOT_ESTABLISHED')

if __name__=='__main__':unittest.main()
