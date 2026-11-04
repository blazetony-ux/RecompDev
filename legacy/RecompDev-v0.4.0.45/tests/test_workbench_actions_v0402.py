"""Tests the actual web action boundary with a synthetic Sega 8-bit ROM."""
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]

class WorkbenchActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        cls.library=cls.root/'roms';(cls.library/'MASTERSYSTEM').mkdir(parents=True)
        cls.rom=cls.library/'MASTERSYSTEM'/'Shinobi (test).sms'
        rom=bytearray(32768)
        rom[0x7ff0:0x7ff8]=b'TMR SEGA'
        cls.rom.write_bytes(rom)
        cls.db=cls.root/'test.sqlite'
        shutil.copyfile(ROOT/'catalogue.sqlite',cls.db)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.base=f'http://127.0.0.1:{cls.port}'
        cls.proc=subprocess.Popen([sys.executable,str(ROOT/'recomp.py'),'--db',str(cls.db),'serve','--port',str(cls.port),'--rom-root',str(cls.library)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                cls.config=cls.read_json('/api/discovery-control')['data']
                break
            except OSError:
                if cls.proc.poll() is not None:raise RuntimeError(cls.proc.stderr.read().decode())
                time.sleep(0.05)
        else:raise RuntimeError('Workbench failed to start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:cls.proc.kill();cls.proc.wait()
        cls.proc.stderr.close()
        cls.temp.cleanup()

    @classmethod
    def read_json(cls,path,headers=None):
        req=Request(cls.base+path,headers=headers or {})
        with urlopen(req,timeout=5) as r:return json.load(r)

    def post(self,path,payload,token=None,origin=None):
        headers={'Content-Type':'application/json','X-RecompDev-Token': token if token is not None else self.config['token'],
                 'Origin':origin if origin is not None else self.base}
        req=Request(self.base+path,data=json.dumps(payload).encode(),headers=headers,method='POST')
        with urlopen(req,timeout=10) as r:return json.load(r)

    def test_00_discovery_page_has_action_panel(self):
        with urlopen(self.base+'/discovery') as r:html=r.read().decode()
        for fragment in ('id="add-rom"','id="scan-selected"','id="rom-browser"','id="job-log"'):
            self.assertIn(fragment,html)

    def test_01_root_and_shinobi_are_visible(self):
        result=self.read_json('/api/discovery-library?folder='+quote(str(self.library/'MASTERSYSTEM')))['data']
        self.assertEqual(len(result['files']),1)
        self.assertEqual(result['files'][0]['path'],str(self.rom))
        self.assertTrue(self.config['token'])
        self.assertEqual(self.config['roots'],[str(self.library)])

    def test_02_security_rejections(self):
        out_of_root=self.root/'out.sms';out_of_root.write_bytes(b'TMR SEGA'+bytes(32760))
        with self.assertRaises(HTTPError) as ctx:
            self.read_json('/api/discovery-library?folder='+quote(str(self.root)))
        self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/discovery-run',{'mode':'file','path':str(out_of_root),'budget':5})
        self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/discovery-run',{'mode':'file','path':str(self.rom),'budget':5},token='incorrect')
        self.assertEqual(ctx.exception.code,403)
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/discovery-run',{'mode':'file','path':str(self.rom),'budget':5},origin='https://example.com')
        self.assertEqual(ctx.exception.code,403)
        with self.assertRaises(HTTPError) as ctx:
            self.post('/api/discovery-run',{'mode':'file','path':str(self.rom),'budget':True})
        self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx:
            self.read_json('/api/discovery-control',headers={'Host':'evil.test'})
        self.assertEqual(ctx.exception.code,403)

    def test_03_launch_job_and_persist_evidence(self):
        before=self.rom.read_bytes()
        job=self.post('/api/discovery-run',{'mode':'file','path':str(self.rom),'budget':20,'max_files':10})['data']
        self.assertIn(job['state'],('RUNNING','COMPLETE'))
        for _ in range(200):
            job=self.read_json('/api/discovery-job')['data']
            if job['state']!='RUNNING':break
            time.sleep(0.07)
        self.assertEqual(job['state'],'COMPLETE',job)
        self.assertTrue(job['report_written'])
        result=self.read_json('/api/discovery')['data']
        targets=[x for x in result['sources'] if x['path']==str(self.rom)]
        self.assertEqual(len(targets),1)
        self.assertEqual(targets[0]['system'],'mastersystem')
        self.assertEqual(targets[0]['coverage_bytes']['STRUCTURE'],16)
        self.assertEqual(self.rom.read_bytes(),before)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.base+'/catalogue.sqlite',timeout=5)
        self.assertEqual(ctx.exception.code,404)

    def test_04_repeat_deduplicates(self):
        self.post('/api/discovery-run',{'mode':'file','path':str(self.rom),'budget':20,'max_files':10})
        for _ in range(200):
            state=self.read_json('/api/discovery-job')['data']['state']
            if state!='RUNNING':break
            time.sleep(0.06)
        self.assertEqual(state,'COMPLETE')
        result=self.read_json('/api/discovery')['data']
        targets=[x for x in result['sources'] if x['path']==str(self.rom)]
        self.assertEqual(len(targets),1)
        self.assertEqual(len([x for x in result['tasks'] if x['source_id']==targets[0]['source_id']]),4)

if __name__=='__main__':unittest.main()
