"""Game-independent dependency/verification regression, no copyrighted ROMs."""
from contextlib import closing

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from nativecore.dependencies import evidence_index, save_graph, frontier
from nativecore.parity import SCHEMA, compare
from nativepilot.generator import sha256


def ins(raw,addr,hexdata,flows=(),fallthrough=None):
    code=bytes.fromhex(hexdata)
    raw[addr:addr+len(code)]=code
    return {'address':addr,'length':len(code),'bytes_sha256':hashlib.sha256(code).hexdigest(),
            'mnemonic':'JR' if flows else 'LD','flows':list(flows),'fallthrough':fallthrough,
            'pcode':[{'op':'COPY','output':{'space':'register','offset':1,'size':1},
                      'inputs':[{'space':'const','offset':1,'size':1}]}]}

class DependencyGraphContracts(unittest.TestCase):
    def make(self,p,other=False):
        raw=bytearray(0x10000)
        seed=ins(raw,0x100,'1802' if not other else '1803',flows=[0x104 if not other else 0x105],fallthrough=0x102)
        nxt=ins(raw,0x102,'3e01')
        raw[0x7ff0:0x7ff8]=b'TMR SEGA'
        p.write_bytes(raw)
        doc={'language':'z80:LE:16:default','source_sha256':sha256(p),
             'target_id':'mastersystem-'+sha256(p)[:12],
             'functions':[{'entry':0x100,'instructions':[seed,nxt]}]}
        return doc

    def test_persists_authenticated_edges_and_isolates_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rom=root/'one.sms';other=root/'two.sms';d1=self.make(rom);d2=self.make(other,True)
            db=root/'graph.sqlite'
            first=save_graph(db,sha256(rom),[d1],rom)
            self.assertEqual(first['authenticated_instructions'],2)
            self.assertGreaterEqual(first['unresolved_edges'],1)
            targets=frontier(db,sha256(rom))
            self.assertTrue(any(t['physical_offset']==0x104 for t in targets))
            save_graph(db,sha256(other),[d2],other)
            self.assertTrue(any(t['physical_offset']==0x105 for t in frontier(db,sha256(other))))
            self.assertEqual(frontier(db,sha256(rom)),targets)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM native_code_nodes_v0410').fetchone()[0],4)
            # Repeated import updates instead of accumulating duplicate graph rows.
            save_graph(db,sha256(rom),[d1],rom)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM native_code_edges_v0410 WHERE source_id=?',(sha256(rom),)).fetchone()[0],2)

    def test_corrupted_hash_rejected_before_graph_db_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rom=root/'other.sms';doc=self.make(rom)
            doc['functions'][0]['instructions'][0]['bytes_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'bytes mismatch'):
                save_graph(root/'bad.sqlite',sha256(rom),[doc],rom)
            self.assertEqual(doc['source_sha256'],sha256(rom))

    def test_fixed_and_banked_physical_addresses_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rom=root/'mapped.sms';raw=bytearray(0x40000)
            a=ins(raw,0x8000,'3e01');b=ins(raw,0x18000,'3e02')
            # Ghidra presents bank 6 instruction at logical 0x8000, but its
            # instruction bytes come from 0x18000 in the original cartridge.
            b['address']=0x8000
            raw[0x7ff0:0x7ff8]=b'TMR SEGA';rom.write_bytes(raw)
            ident=sha256(rom)
            original={'language':'z80:LE:16:default','source_sha256':ident,
                'target_id':'mastersystem-test','functions':[{'entry':0x8000,'instructions':[a]}]}
            overlay={'language':'z80:LE:16:default','source_sha256':ident,
                'target_id':'mastersystem-test','bank_context':{'slot':2,'bank':6,'base':0x8000,'physical_start':0x18000},
                'functions':[{'entry':0x8000,'instructions':[b]}]}
            nodes,edges,indirect=evidence_index([original,overlay],rom)
            self.assertEqual(set(nodes),{0x8000,0x18000})
            self.assertEqual(nodes[0x18000]['bank'],6)

class ExternalParityRules(unittest.TestCase):
    def test_never_claims_parity_without_independent_evidence(self):
        source='a'*64
        candidate={'source_id':source,'trace':{'checkpoints':[{'step':10,'pc':0x38,'af':5}]}}
        with self.assertRaisesRegex(ValueError,'provenance'):
            compare({'schema':SCHEMA,'source_sha256':source,'checkpoints':[{'step':10,'pc':0x38}]},candidate)
        external={'schema':SCHEMA,'source_sha256':source,'independent_source':'owner supplied external reference',
                  'checkpoints':[{'step':10,'pc':0x38,'af':6}]}
        result=compare(external,candidate)
        self.assertEqual(result['status'],'DIVERGED')
        self.assertEqual(result['mismatches'][0]['field'],'af')
        external['checkpoints'][0]['af']=5
        self.assertEqual(compare(external,candidate)['status'],'MATCHED_SAMPLED_CHECKPOINTS')

if __name__=='__main__':unittest.main()
