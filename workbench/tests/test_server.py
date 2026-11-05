"""Read-only Workbench security and API behaviour with a real SQLite fixture."""
from __future__ import annotations
import hashlib
from contextlib import closing
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from workbench.server import WorkbenchServer, query_table, read_only_db, tables

class TestWorkbench(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='recomp-workbench-')
        self.db=Path(self.tmp.name)/'fixture.sqlite'
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('CREATE TABLE "weird table"("value" TEXT, n INTEGER, blob BLOB)')
            con.executemany('INSERT INTO "weird table" VALUES(?,?,?)',[
                ('hello',1,b'\x01\x02'),('<script>alert(1)</script>',2,b'\x00'),
                ('hello world',3,b'')])
            con.commit()
        self.original=hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.server=WorkbenchServer(('127.0.0.1',0),self.db,'my-test-token')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.root=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.assertEqual(self.original,hashlib.sha256(self.db.read_bytes()).hexdigest())
        self.tmp.cleanup()

    def get(self,path,token='my-test-token'):
        delim='&' if '?' in path else '?'
        return urllib.request.urlopen(self.root+path+delim+'token='+token,timeout=3)

    def test_read_only_catalogue_and_html_escape(self):
        body=self.get('/').read().decode()
        self.assertIn('weird table',body)
        self.assertIn('READ ONLY',body)
        body=self.get('/table/'+urllib.parse.quote('weird table')).read().decode()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',body)
        self.assertNotIn('<script>alert(1)</script>',body)
        self.assertIn('BLOB (2 bytes)',body)

    def test_api_filter_and_bounded_paging(self):
        table=urllib.parse.quote('weird table')
        data=json.loads(self.get('/api/table/'+table+'?column=value&contains=hello&limit=1').read())
        self.assertEqual(len(data['rows']),1)
        self.assertTrue(data['has_next'])
        self.assertEqual(data['rows'][0]['blob'],{'type':'blob','bytes':2})
        data=json.loads(self.get('/api/table/'+table+'?column=value&contains=hello&limit=1&offset=1').read())
        self.assertEqual(data['rows'][0]['value'],'hello world')
        with self.assertRaises(urllib.error.HTTPError) as bad:
            self.get('/api/table/'+table+'?column=evil&contains=hi')
        self.assertEqual(bad.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as bad:
            self.get('/api/table/'+table+'?limit=100000')
        self.assertEqual(bad.exception.code,400)

    def test_token_required_no_write_routes(self):
        with self.assertRaises(urllib.error.HTTPError) as bad:self.get('/',token='wrong')
        self.assertEqual(bad.exception.code,403)
        request=urllib.request.Request(self.root+'/?token=my-test-token',data=b'INSERT',method='POST')
        with self.assertRaises(urllib.error.HTTPError) as bad:urllib.request.urlopen(request,timeout=3)
        self.assertEqual(bad.exception.code,405)

    def test_readonly_sqlite_rejects_writes(self):
        with closing(read_only_db(self.db)) as con:
            self.assertEqual(tables(con),['weird table'])
            with self.assertRaises(sqlite3.OperationalError):
                con.execute('DELETE FROM "weird table"')
            self.assertEqual(len(query_table(con,'weird table')['rows']),3)

if __name__=='__main__':unittest.main()
