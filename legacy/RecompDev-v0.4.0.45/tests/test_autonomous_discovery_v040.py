import json
import sqlite3
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from discovery import formats,store
from discovery.engine import run, identity,ingest_function_campaign
from discovery.image import png_rgba,render_tim,render_md_tiles


def make_tim():
    # TIM: 4bpp, one row of 4 pixels with one 16-colour CLUT.
    colors=[0x001F,0x03E0,0x7C00]+[0]*13
    clut=struct.pack('<IHHHH',44,0,0,16,1)+struct.pack('<16H',*colors)
    pixels=struct.pack('<IHHHH',14,0,0,1,1)+b'\x10\x21'
    return b'\x10\x00\x00\x00'+struct.pack('<I',8)+clut+pixels


def iso_record(extent,length,name,is_dir):
    n=name.encode('ascii')
    size=33+len(n)+(1 if len(n)%2==0 else 0)
    r=bytearray(size)
    r[0]=size;r[2:6]=extent.to_bytes(4,'little');r[6:10]=extent.to_bytes(4,'big')
    r[10:14]=length.to_bytes(4,'little');r[14:18]=length.to_bytes(4,'big')
    r[25]=2 if is_dir else 0;r[28:30]=b'\x01\x00';r[30:32]=b'\x00\x01'
    r[32]=len(n);r[33:33+len(n)]=n
    return bytes(r)


def make_iso(path,raw=False):
    size=64*2048;disc=bytearray(size)
    pvd=bytearray(2048);pvd[:7]=b'\x01CD001\x01'
    pvd[40:72]=b'RECOMPDEV TEST'.ljust(32,b' ')
    pvd[156:156+34]=iso_record(20,2048,'\x00',True)
    disc[16*2048:17*2048]=pvd
    folder=iso_record(20,2048,'\x00',True)+iso_record(20,2048,'\x01',True)+iso_record(22,len(make_tim()),'ART.TIM;1',False)
    disc[20*2048:20*2048+len(folder)]=folder
    tim=make_tim();disc[22*2048:22*2048+len(tim)]=tim
    if raw:
        physical=bytearray(64*2352)
        for i in range(64):physical[i*2352+24:i*2352+24+2048]=disc[i*2048:(i+1)*2048]
        path.write_bytes(physical)
    else:path.write_bytes(disc)


class TestDiscoveryV040(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.db=self.root/'store.sqlite'

    def test_png_and_tim_roundtrip(self):
        raw=make_tim();fmt,w,h,pixels,n=render_tim(raw)
        self.assertEqual(('PS1_TIM_4BPP',4,1,len(raw)),(fmt,w,h,n))
        self.assertEqual(pixels[:4],bytes((255,0,0,255)))
        self.assertTrue(png_rgba(w,h,pixels).startswith(b'\x89PNG'))

    def test_reject_truncated_tim(self):
        with self.assertRaises(ValueError):render_tim(make_tim()[:-2])
        with self.assertRaises(ValueError):render_tim(b'not a valid TIM')
        with self.assertRaises(ValueError):png_rgba(4,4,b'\x00')

    def test_md_header_and_format_region(self):
        rom=self.root/'sample.md';raw=bytearray(0x10000)
        raw[0x100:0x104]=b'SEGA';raw[0x120:0x12C]=b'TEST ROM 123'
        # High diversity at a candidate-aligned ROM region
        raw[0x200:0x400]=bytes([i%128 for i in range(512)])
        rom.write_bytes(raw)
        result=run(self.db,[],[rom],self.root/'out')
        self.assertEqual(result['sources'][0]['system'],'megadrive')
        self.assertEqual(result['sources'][0]['coverage_bytes']['STRUCTURE'],512)
        self.assertEqual(result['run']['tasks_executed'],5)
        self.assertGreaterEqual(len(result['assets']),1)
        self.assertEqual(result['assets'][0]['confidence'],'HEURISTIC_UNVERIFIED')
        self.assertTrue(Path(result['assets'][0]['preview_path']).is_file())
        self.assertEqual(sum(result['sources'][0]['coverage_bytes'].values()),rom.stat().st_size)
        self.assertTrue(any(t['status']=='NEEDS_EVIDENCE' for t in result['tasks']))
        # Second run should be zero-work, and records aren't duplicated.
        result2=run(self.db,[],[rom],self.root/'out')
        self.assertEqual(result2['run']['tasks_executed'],0)
        self.assertEqual(len(result['assets']),len(result2['assets']))

    def test_psx_exe_tim_extract_and_preview(self):
        exe=self.root/'boot.psx';data=bytearray(0x900)
        data[:8]=b'PS-X EXE';off=0x800;tim=make_tim();data[off:off+len(tim)]=tim
        exe.write_bytes(data)
        result=run(self.db,[],[exe],self.root/'out')
        self.assertEqual(result['sources'][0]['system'],'psx-exe')
        self.assertEqual(len(result['assets']),1)
        self.assertEqual(result['assets'][0]['confidence'],'STRUCTURALLY_VALIDATED')
        self.assertTrue(Path(result['assets'][0]['preview_path']).is_file())
        self.assertEqual(result['sources'][0]['coverage_bytes']['ASSET'],len(tim))

    def test_iso_2048_and_raw_2352_extract(self):
        for raw in (False,True):
            with self.subTest(raw=raw):
                path=self.root/('disc.img' if raw else 'disc.iso')
                make_iso(path,raw)
                iso=formats.IsoReader(path)
                self.assertTrue(iso.valid())
                self.assertEqual(iso.sector_size,2352 if raw else 2048)
                self.assertEqual(len(iso.files()),1)
                result=run(self.db,[],[path],self.root/'out')
                self.assertEqual(result['sources'][0]['system'],'iso9660')
                self.assertEqual(result['disc_files'],1 if not raw else 2)
                self.assertGreaterEqual(len(result['assets']),1)
                if raw:self.assertEqual(result['sources'][0]['coverage_bytes']['ASSET'],0)

    def test_task_dependencies_and_budget_resume(self):
        exe=self.root/'x.psx';exe.write_bytes(b'PS-X EXE'+b'\x00'*2048)
        first=run(self.db,[],[exe],self.root/'out',budget=1)
        self.assertEqual(first['run']['tasks_executed'],1)
        self.assertEqual(first['task_status_counts'].get('READY'),3)
        second=run(self.db,[],[exe],self.root/'out')
        self.assertEqual(second['run']['tasks_executed'],3)

    def test_source_revision_creates_new_jobs_without_erasing_history(self):
        source=self.root/'updated.psx'
        source.write_bytes(b'PS-X EXE'+b'\x00'*2048)
        first=run(self.db,[],[source],self.root/'out')
        old=first['sources'][0]['source_id']
        source.write_bytes(b'PS-X EXE'+b'\x01'*2048)
        second=run(self.db,[],[source],self.root/'out')
        self.assertEqual(len(second['sources']),2)
        self.assertEqual(len(set(x['source_id'] for x in second['sources'])),2)
        self.assertEqual(second['run']['tasks_executed'],4)
        self.assertTrue(any(x['source_id']==old for x in second['sources']))

    def test_no_source_mutation(self):
        source=self.root/'x.psx';source.write_bytes(b'PS-X EXE'+b'\x00'*2048)
        original=source.read_bytes()
        run(self.db,[],[source],self.root/'out')
        self.assertEqual(source.read_bytes(),original)

    def test_metadata_only_for_unknown_container(self):
        unknown=self.root/'crazy.chd';unknown.write_bytes(b'MComprHD'+b'\x00'*100)
        res=run(self.db,[],[unknown],self.root/'out')
        self.assertEqual(res['sources'][0]['system'],'chd')
        self.assertEqual(len(res['assets']),0)
        self.assertGreater(res['sources'][0]['coverage_bytes']['UNKNOWN'],0)

    def test_campaign_function_backlog_is_persistent(self):
        source=self.root/'demo.psx';source.write_bytes(b'PS-X EXE'+b'\x00'*2048)
        sha,kind=identity(source)
        con=store.connect(self.db)
        with con:
            con.execute('CREATE TABLE targets(target_id TEXT PRIMARY KEY,source_sha256 TEXT)')
            con.execute('INSERT INTO targets VALUES (?,?)',('t1',sha))
        con.close()
        report=self.root/'campaign.json'
        report.write_text(json.dumps({'schema':'recomp-function-campaign-v0.3.2.3','jobs':[
          {'target_id':'t1','entry':0x80010000,'compile_status':'BLOCKED_UNSUPPORTED_SEMANTICS',
           'blocker':'delay_slot_requires_isa_qualification'},
          {'target_id':'t1','entry':0x80020000,'compile_status':'COMPILED_SEEDED_SMOKE_ONLY',
           'verification_status':'ORIGINAL_VS_NATIVE_NOT_RUN'}]}))
        res=run(self.db,[],[source],self.root/'out',campaign=report)
        self.assertEqual(res['run']['previous_function_campaign']['imported'],2)
        self.assertIn('NEEDS_CAPABILITY',res['task_status_counts'])
        again=run(self.db,[],[source],self.root/'out',campaign=report)
        self.assertEqual(again['run']['tasks_executed'],0)

    def test_workbench_discovery_api_reads_metadata(self):
        source=self.root/'x.psx';source.write_bytes(b'PS-X EXE'+b'\x00'*2048)
        run(self.db,[],[source],self.root/'out')
        from workbench import data
        con=sqlite3.connect(self.db)
        con.row_factory=sqlite3.Row
        try:
            value=data(con,'discovery',{})
            self.assertEqual(value['schema'],'recomp-autonomous-discovery-v0.4.0')
            self.assertEqual(len(value['sources']),1)
        finally:con.close()

    def test_byte_coverage_does_not_double_count_overlaps(self):
        source=self.root/'file.bin';source.write_bytes(b'X'*100)
        sha,_=identity(source);con=store.connect(self.db)
        store.store_source(con,sha,source,100,'SHA256_COMPLETE','unknown',source.name,'test')
        store.region(con,sha,0,50,'STRUCTURE','VALIDATED_STRUCTURE',{'a':1})
        store.region(con,sha,25,60,'ASSET_CANDIDATE','HEURISTIC_UNVERIFIED',{'a':2})
        counts=store.summary(con)['sources'][0]['coverage_bytes']
        self.assertEqual(counts['STRUCTURE'],50)
        self.assertEqual(counts['ASSET_CANDIDATE'],35)
        self.assertEqual(counts['UNKNOWN'],15)
        self.assertEqual(sum(counts.values()),100)
        con.close()

if __name__=='__main__':unittest.main()
