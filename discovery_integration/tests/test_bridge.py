"""Synthetic ISA, filesystem, source-identity and negative provenance regressions."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from contextlib import closing
import sqlite3
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / 'legacy' / 'RecompDev-v0.4.0.45'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LEGACY))
from discovery import engine, store
from discovery_integration import CONTRACT
from discovery_integration.registry import load
from discovery_integration.bridge import audit
from discovery_integration.providers import catalogue, disc, structure


def md_bytes():
    b=bytearray(0x500)
    b[0x100:0x104]=b'SEGA'
    b[4:8]=(0x200).to_bytes(4,'big')
    return bytes(b)


def psx_bytes():
    b=bytearray(0x808)
    b[:8]=b'PS-X EXE'
    struct.pack_into('<III', b,0x10,0x80010000,0,0x80010000)
    struct.pack_into('<I', b,0x1c,8)
    return bytes(b)


def record(name: bytes, extent: int, size: int, *, directory: bool=False) -> bytes:
    n=34+len(name)+(len(name)%2)
    r=bytearray(n)
    r[0]=n;r[2:6]=extent.to_bytes(4,'little');r[6:10]=extent.to_bytes(4,'big')
    r[10:14]=size.to_bytes(4,'little');r[14:18]=size.to_bytes(4,'big')
    r[25]=2 if directory else 0
    r[28:30]=(1).to_bytes(2,'little');r[30:32]=(1).to_bytes(2,'big')
    r[32]=len(name);r[33:33+len(name)]=name
    return bytes(r)


def iso_bytes(sector_size: int):
    logical=bytearray(2048*24)
    pvd=16*2048
    logical[pvd]=1;logical[pvd+1:pvd+6]=b'CD001';logical[pvd+6]=1
    logical[pvd+40:pvd+46]=b'TESTCD'
    root=record(b'\x00',20,2048,directory=True)
    logical[pvd+156:pvd+156+len(root)]=root
    d=20*2048
    file=record(b'BOOT.EXE;1',21,len(psx_bytes()))
    logical[d:d+len(file)]=file
    logical[21*2048:21*2048+len(psx_bytes())]=psx_bytes()
    if sector_size==2048:
        return bytes(logical)
    data=bytearray(sector_size*24)
    # ISO9660 MODE2/Form1: 24-byte leading sector metadata.
    for sector in range(24):
        data[sector*2352+24:sector*2352+24+2048]=logical[sector*2048:(sector+1)*2048]
    return bytes(data)


class DiscoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rd-uni-discovery-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_provider_registry_loads_versioned_roles(self):
        providers=load()
        self.assertEqual(set(providers), {'structure','catalogue','disc'})
        self.assertEqual(providers['structure'].identifier,'legacy.structure.v1')

    def test_untrusted_provider_module_path_is_rejected(self):
        doc=json.loads((ROOT/'discovery_integration/providers.json').read_text())
        doc['providers'][0]['module']='os'
        path=self.root/'registry.json';path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'outside'):
            load(path)

    def test_m68k_entry_read_from_structural_header_not_name(self):
        path=self.root/'anything.bin';path.write_bytes(md_bytes())
        r=structure.analyze(path,LEGACY)
        self.assertEqual(r['format'],'megadrive')
        self.assertEqual(r['isa_candidate'],'m68k')
        self.assertEqual(r['mapping_status'],'STATIC_ENTRY_VALIDATED')
        self.assertEqual(r['entry'],0x200)

    def test_sms_header_preserved_without_native_parity_claim(self):
        path=self.root/'random.sms'
        b=bytearray(0x8000);b[0x7ff0:0x7ff8]=b'TMR SEGA'
        path.write_bytes(b)
        r=structure.analyze(path,LEGACY)
        self.assertEqual(r['isa_candidate'],'z80')
        self.assertNotEqual(r.get('mapping_status'),'STATIC_ENTRY_VALIDATED')

    def test_invalid_m68k_reset_entry_is_blocked_not_inferred(self):
        path=self.root/'not-a-game.md';b=bytearray(md_bytes());b[4:8]=(0xFFFFFF).to_bytes(4,'big')
        path.write_bytes(b)
        r=structure.analyze(path,LEGACY)
        self.assertEqual(r['mapping_status'],'BLOCKED_INVALID_EXECUTABLE_MAPPING')

    def test_psx_direct_exe_static_mapping(self):
        path=self.root/'abstract.exe';path.write_bytes(psx_bytes())
        r=structure.analyze(path,LEGACY)
        self.assertEqual(r['isa_candidate'],'mips')
        self.assertEqual(r['mapping_status'],'STATIC_ENTRY_VALIDATED')
        self.assertEqual(r['entry'],0x80010000)

    def test_iso_disc_raw_and_standard_validate_same_exe(self):
        for sector in (2048,2352):
            with self.subTest(sector=sector):
                path=self.root/f'disc-{sector}.img';path.write_bytes(iso_bytes(sector))
                s=structure.analyze(path,LEGACY)
                self.assertEqual(s['format'],'iso9660')
                d=disc.scan(path,LEGACY)
                self.assertEqual(d['sector_size'],sector)
                self.assertEqual(d['inventory_count'],1)
                self.assertEqual(len(d['candidates']),1)
                exe=d['candidates'][0]
                self.assertEqual(exe['status'],'STATIC_ENTRY_VALIDATED')
                self.assertEqual(exe['entry'],0x80010000)
                self.assertEqual(d['extracted_files'],0)
                self.assertEqual(exe['sha256'],hashlib.sha256(psx_bytes()).hexdigest())

    def test_export_is_explicit_and_bounded(self):
        path=self.root/'disc.img';path.write_bytes(iso_bytes(2352))
        dest=self.root/'private'
        r=disc.scan(path,LEGACY,export_dir=dest)
        self.assertEqual(r['extracted_files'],1)
        self.assertEqual(len(list(dest.glob('*'))),1)
        self.assertEqual(next(dest.iterdir()).read_bytes(),psx_bytes())

    def test_catalogue_source_scope_and_uncached_report(self):
        path=self.root/'one.md';path.write_bytes(md_bytes())
        another=self.root/'two.md';b=bytearray(md_bytes());b[0x250]=1;another.write_bytes(b)
        db=self.root/'working.sqlite'
        # sqlite3.Connection.__exit__ commits but does NOT close the handle.
        # On Windows an open SQLite handle prevents TemporaryDirectory cleanup.
        with closing(store.connect(db)) as con:
            sid,kind=engine.identity(path)
            sid2,kind2=engine.identity(another)
            store.store_source(con,sid,path,path.stat().st_size,kind,'megadrive','one','header')
            store.store_source(con,sid2,another,another.stat().st_size,kind2,'megadrive','two','header')
            task=store.task(con,sid,'resolve_function_dispatch',priority=55)
            store.state(con,task,'NEEDS_EVIDENCE','dispatch unresolved')
            store.state(con,store.task(con,sid2,'unrelated_task'), 'NEEDS_ADAPTER','separate input')
        # Keep this Windows-relevant regression explicit on platforms without
        # mandatory SQLite file-locking as well.
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute('SELECT 1')
        report=self.root/'discovery-report.json'
        report.write_text(json.dumps({'run':{'tasks_executed':0}}))
        result=audit(path,db,report,self.root/'report',legacy_root=LEGACY)
        self.assertEqual(result['schema'],CONTRACT)
        self.assertEqual(result['outstanding_tasks'],1)
        self.assertEqual(result['discovery_progress'],'NO_NEW_LEGACY_TASKS_EXECUTED')
        meta=json.loads((self.root/'report/universal-discovery.json').read_text())
        self.assertEqual(meta['cache']['outstanding'][0]['kind'],'resolve_function_dispatch')
        self.assertFalse(meta['fresh_work_for_this_input_verified'])
        self.assertFalse(meta['hardware_parity_qualified'])
        with self.assertRaises(FileExistsError):audit(path,db,report,self.root/'report',legacy_root=LEGACY)
        invalid=self.root/'bad.md';invalid.write_bytes(b'not the same')
        r=catalogue.inspect(invalid,db,LEGACY)
        self.assertFalse(r['matching_source_record'])

    def test_no_or_fake_task_count_blocks_false_claim(self):
        path=self.root/'one.md';path.write_bytes(md_bytes())
        db=self.root/'working.sqlite'
        store.connect(db).close()
        report=self.root/'bad-report.json';report.write_text(json.dumps({'run':{'tasks_executed':'passed'}}))
        with self.assertRaisesRegex(ValueError,'task count'):
            audit(path,db,report,self.root/'output',legacy_root=LEGACY)


if __name__=='__main__':unittest.main()
