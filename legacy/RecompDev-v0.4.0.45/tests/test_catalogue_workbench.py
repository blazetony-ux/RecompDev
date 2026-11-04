"""Synthetic contract tests; no proprietary game binaries used."""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from graph_store import connect, import_flow,import_analyzer,register_target_if_absent,import_scan
from adapters.formats import Image,open_image
from adapters.flow import classify
from scan_graph import discover
from workbench import data

ROOT=Path(__file__).resolve().parents[1]

class FakeEngine:
    def disasm(self,blob,pc,count=1):
        if len(blob)<4:return iter(())
        return iter((SimpleNamespace(address=pc,size=4,bytes=blob[:4],mnemonic='nop',op_str=''),))

class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'c.sqlite'
        shutil.copyfile(ROOT/'catalogue.sqlite',self.db)
        self.con=connect(self.db);self.addCleanup(self.con.close)

    def test_historical_targets_preserved(self):
        self.assertGreaterEqual(self.con.execute('SELECT count(*) FROM targets').fetchone()[0],2)
        self.assertGreaterEqual(self.con.execute('SELECT count(*) FROM observations').fetchone()[0],218)
        self.assertEqual(self.con.execute('SELECT count(*) FROM candidate_forms').fetchone()[0],753)

    def test_historical_graph_import_idempotent(self):
        f=ROOT/'seed/sonic-flow-evidence.json'
        a=import_flow(self.con,f);b=import_flow(self.con,f)
        self.assertEqual(a,b)
        self.assertEqual(self.con.execute('SELECT count(*) FROM graph_runs WHERE run_id=?',(a,)).fetchone()[0],1)

    def test_historical_calls_are_static_not_verified(self):
        a=data(self.con,'overview',{})['totals'];self.assertGreaterEqual(a['targets'],2)
        self.assertGreaterEqual(a['calls'],5);self.assertGreaterEqual(a['function_candidates'],6)
        calls=data(self.con,'calls',{'target':['megadrive-46160baa0636']})
        self.assertGreaterEqual(len(calls),5)
        self.assertTrue(all(r['evidence']=='static_reachable' for r in calls))
        self.assertTrue(all(r['kind'] in ('direct_call','indirect_call') for r in calls))
        ridge=data(self.con,'calls',{'target':['psx-exe-bde353330bf4']})
        self.assertTrue(all(r['kind'] in ('direct_call','indirect_call') for r in ridge))

    def test_identity_conflict_rejected(self):
        d=json.loads((ROOT/'seed/sonic-flow-evidence.json').read_text())
        d['source_sha256']='0'*64
        fn=Path(self.tmp.name)/'wrong.json';fn.write_text(json.dumps(d))
        with self.assertRaises(ValueError):import_flow(self.con,fn)

    def test_existing_address_provenance_must_be_real(self):
        d=json.loads((ROOT/'seed/sonic-flow-evidence.json').read_text())
        d['edges'].append({'source':0x123456,'target':0x300,'kind':'direct_call'})
        fn=Path(self.tmp.name)/'fake.json';fn.write_text(json.dumps(d))
        with self.assertRaises(ValueError):import_flow(self.con,fn)

    def test_external_analyzer_observations_separated(self):
        tid='psx-exe-bde353330bf4';sha=self.con.execute('SELECT source_sha256 FROM targets WHERE target_id=?',(tid,)).fetchone()[0]
        d={'schema':'recomp-analyzer-discovery-v1','target_id':tid,'source_sha256':sha,'analyzer':'synthetic-ghidra',
           'functions':[{'entry':0x80040004,'name':'entry'},{'entry':0x80041000,'name':'callee'}],
           'calls':[{'source':0x80040020,'target':0x80041000,'kind':'direct_call','caller_entry':0x80040004},
                    {'source':0x80040024,'target':None,'kind':'indirect_call','caller_entry':0x80040004}]}
        f=Path(self.tmp.name)/'external.json';f.write_text(json.dumps(d))
        run_id=import_analyzer(self.con,f)
        self.assertEqual(import_analyzer(self.con,f),run_id)
        self.assertEqual(self.con.execute('SELECT count(*) FROM graph_transfers WHERE run_id=?',(run_id,)).fetchone()[0],2)
        fns=data(self.con,'functions',{'run':[run_id]})
        self.assertEqual({x['label'] for x in fns},{'entry','callee'})

    def test_external_identity_fail_closed(self):
        d={'schema':'recomp-analyzer-discovery-v1','target_id':'psx-exe-bde353330bf4','source_sha256':'0'*64,
           'analyzer':'test','functions':[],'calls':[]}
        f=Path(self.tmp.name)/'wrong.json';f.write_text(json.dumps(d))
        with self.assertRaises(ValueError):import_analyzer(self.con,f)

    def test_readonly_sqlite_connection_rejects_mutation(self):
        ro=connect(self.db,readonly=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("DELETE FROM targets")
        finally:ro.close()

    def test_all_forms_accessible(self):
        forms=data(self.con,'forms',{'limit':['2000']})
        self.assertEqual(len(forms),753)
        sonic=data(self.con,'forms',{'target':['megadrive-46160baa0636'],'limit':['2000']})
        self.assertGreater(len(sonic),0)
        self.assertTrue(all(f['form_key'].startswith('m68k|') for f in sonic))

    def test_mips_delay_slot_and_call_return_site(self):
        base=0x80040000;raw=bytearray(0x40)
        def w(off,val):raw[off:off+4]=val.to_bytes(4,'little')
        # JAL 0x80040020; slot NOP; JR RA at +8; slot NOP; callee JR RA at +0x24
        w(0,0x0C010008);w(8,0x03E00008);w(0x24,0x03E00008)
        im=Image('raw','mips','little',base,base+len(raw),0,base,4,bytes(raw),())
        obs,edges,barriers=discover(im,FakeEngine(),100)
        self.assertGreaterEqual(len(obs),6)
        self.assertIn({'source':base,'target':base+0x20,'kind':'direct_call','inside_region':True},edges)
        self.assertIn({'source':base,'target':base+0x08,'kind':'return_site','inside_region':True},edges)
        self.assertIn({'source':base,'target':base+4,'kind':'delay_slot','inside_region':True},edges)
        self.assertFalse(any('delay slot not yet traversed' in x['reason'] for x in barriers))

    def test_mips_indirect_calls_remain_indirect(self):
        ins=SimpleNamespace(bytes=(0x0060f809).to_bytes(4,'little'),address=0x80040000,size=4)
        im=SimpleNamespace(isa='mips')
        f=classify(im,ins)
        self.assertEqual(f.kind,'indirect_call')
        self.assertIn((None,'indirect_call'),f.edges)
        self.assertEqual(f.barrier,'register call target unknown')

    def test_synthetic_m68k_direct_jsr(self):
        im=SimpleNamespace(isa='m68k')
        ins=SimpleNamespace(bytes=bytes.fromhex('4eb900000300'),size=6,address=0x200)
        f=classify(im,ins)
        self.assertEqual(f.kind,'call')
        self.assertIn((0x300,'direct_call'),f.edges)
        self.assertIn((0x206,'return_site'),f.edges)

    def test_fresh_scan_and_catalogue_are_cross_target(self):
        from unittest.mock import patch
        from scan_graph import run
        b=bytearray(0x840)
        b[:8]=b'PS-X EXE'
        b[0x10:0x14]=(0x80040000).to_bytes(4,'little')
        b[0x18:0x1c]=(0x80040000).to_bytes(4,'little')
        b[0x1c:0x20]=(0x40).to_bytes(4,'little')
        b[0x800:0x804]=(0x0c010008).to_bytes(4,'little')
        b[0x808:0x80c]=(0x03e00008).to_bytes(4,'little')
        b[0x824:0x828]=(0x03e00008).to_bytes(4,'little')
        source=Path(self.tmp.name)/'synthetic-psx.exe';source.write_bytes(b)
        with patch('scan_graph.make_capstone',return_value=FakeEngine()):
            result=run(source,self.db,Path(self.tmp.name)/'out',max_instructions=50)
        self.assertGreaterEqual(result['instructions'],6)
        obs=json.loads((Path(self.tmp.name)/'out/observations.json').read_text())
        self.assertTrue(all('bytes' not in x for x in obs['records']))
        results=data(self.con,'calls',{'target':[result['target_id']]})
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['dest'],0x80040020)

    def test_psx_exe_binary_header_validation(self):
        b=bytearray(0x900);b[:8]=b'PS-X EXE';b[0x10:0x14]=(0x80040004).to_bytes(4,'little')
        b[0x18:0x1c]=(0x80040000).to_bytes(4,'little');b[0x1c:0x20]=(0x100).to_bytes(4,'little')
        image=open_image(bytes(b))
        self.assertEqual(image.entry,0x80040004)
        b[0x1c:0x20]=(0xffff).to_bytes(4,'little')
        with self.assertRaises(ValueError):open_image(bytes(b))

if __name__=='__main__':unittest.main()
