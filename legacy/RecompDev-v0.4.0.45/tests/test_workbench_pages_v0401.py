"""Regression: dedicated workspaces, stable routes and read-only browser policy."""
from contextlib import closing

import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]

class WorkbenchPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        db=Path(cls.temp.name)/'browser.sqlite'
        shutil.copyfile(ROOT/'catalogue.sqlite',db)
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
        cls.proc=subprocess.Popen([sys.executable,str(ROOT/'recomp.py'),'--db',str(db),'serve','--port',str(cls.port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        cls.base=f'http://127.0.0.1:{cls.port}'
        for _ in range(100):
            try:
                with urlopen(cls.base+'/',timeout=0.5) as response:
                    if response.status==200:break
            except OSError:
                if cls.proc.poll() is not None:raise RuntimeError(cls.proc.stderr.read().decode())
                time.sleep(0.05)
        else:raise RuntimeError('Workbench failed to start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:cls.proc.kill();cls.proc.wait()
        cls.proc.stderr.close();cls.temp.cleanup()

    def get(self,path):
        with urlopen(self.base+path,timeout=5) as response:
            return response.status,response.headers, response.read().decode()

    def test_catalogue_has_only_five_evidence_tabs(self):
        status,_,body=self.get('/')
        self.assertEqual(status,200)
        self.assertEqual(body.count('role="tab"'),5)
        self.assertNotIn('id="tab-discovery"',body)
        self.assertNotIn('id="tab-functions-v031"',body)
        self.assertIn('href="/discovery"',body)
        self.assertIn('href="/native"',body)

    def test_discovery_is_own_page_with_three_sections(self):
        status,headers,body=self.get('/discovery')
        self.assertEqual(status,200)
        self.assertIn('text/html',headers['Content-Type'])
        self.assertIn('aria-current="page"',body)
        for v in ('id="coverage"','id="assets"','id="backlog"','id="source-filter"','id="task-status"','id="asset-confidence"'):
            self.assertIn(v,body)
        self.assertIn('/static/discovery.js',body)
        self.assertNotIn('role="tab"',body)
        self.assertIn('default-src',headers.get('Content-Security-Policy',''))

    def test_native_is_separate_page(self):
        status,_,body=self.get('/native')
        self.assertEqual(status,200)
        self.assertIn('id="native-results"',body)
        self.assertIn('id="batch-results"',body)
        self.assertIn('/static/native.js',body)

    def test_javascript_and_json_routes(self):
        for path in ('/static/app.js','/static/native.js','/static/discovery.js','/api/discovery','/api/overview'):
            status,_,body=self.get(path)
            self.assertEqual(status,200,path)
            self.assertTrue(body,path)
        self.assertIn('"ok": true',self.get('/api/discovery')[2])

    def test_importer_prefers_existing_discovery_evidence(self):
        from discovery import store
        from tools.import_previous_catalogue import import_best
        root=Path(self.temp.name)
        previous=root/'previous-v040.sqlite'
        older=root/'older-function-only.sqlite'
        out=root/'fresh-v0401.sqlite'
        shutil.copyfile(ROOT/'catalogue.sqlite',previous)
        shutil.copyfile(ROOT/'catalogue.sqlite',older)
        with closing(store.connect(previous)) as con:
            store.store_source(con,'sample-identity','C:/Roms/Fixture.md',8192,'SHA256_COMPLETE',
                               'megadrive','FIXTURE','synthetic test')
        import sqlite3
        with closing(sqlite3.connect(older)) as con, con:
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'conversion_v031' not in tables:
                con.execute('CREATE TABLE conversion_v031 (id INTEGER)')
                con.executemany('INSERT INTO conversion_v031 VALUES(?)',[(i,) for i in range(12)])
        result=import_best([older,previous],out,root/'stamp.json')
        self.assertEqual(result['source'],str(previous.resolve()))
        with closing(sqlite3.connect(out)) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM discovery_sources').fetchone()[0],1)

    def test_original_sources_remain_inaccessible(self):
        for path in ('/catalogue.sqlite','/evidence/file.bin','/static/../catalogue.sqlite','/api/discovery-preview/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'):
            with self.subTest(path=path),self.assertRaises(HTTPError) as h:
                urlopen(self.base+path,timeout=5)
            self.assertEqual(h.exception.code,404)

if __name__=='__main__':unittest.main()
