"""Compiled-byte synthetic multi-ISA discovery, provenance and fail-closed regression.

Uses real M68K/MIPS instruction encodings and the production flow/recovery code;
only Capstone's decoding interface is emulated when Capstone isn't installed.
"""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.formats import Image
from scan_graph import discover
from discovery_benchmark import benchmark
from graph_store import connect, import_flow


def m68k(*words):
    return b''.join(int(w).to_bytes(2,'big') for w in words)

def mips(*words):
    return b''.join(int(w).to_bytes(4,'little') for w in words)

class Engine:
    """Decode the exact limited instructions used by these regression fixtures."""
    def __init__(self,isa):self.isa=isa
    def disasm(self,blob,pc,count=1):
        if self.isa=='mips':
            if len(blob)<4:return iter(())
            return iter((SimpleNamespace(address=pc,size=4,bytes=blob[:4],mnemonic='mips',op_str=''),))
        if len(blob)<2:return iter(())
        first=int.from_bytes(blob[:2],'big')
        n=6 if first in (0x207c,0x227c,0x41f9,0x43f9) else 4 if first in (0x4efa,0x4eba,0x41fa,0x41f8) else 2
        if len(blob)<n:return iter(())
        return iter((SimpleNamespace(address=pc,size=n,bytes=blob[:n],mnemonic='m68k',op_str=''),))

class CrossISARecovery(unittest.TestCase):
    def check(self,isa,data,base,entry,expected_source,expected_target,expected_pattern,expected_count):
        image=Image('raw',isa,'big' if isa=='m68k' else 'little',base,base+len(data),0,entry,2 if isa=='m68k' else 4,data,())
        engine=Engine(isa)
        old,_,oldbar=discover(image,engine,100)
        proofs=[];new,edges,newbar=discover(image,engine,100,(),True,proofs)
        self.assertNotIn(expected_target,{x['address'] for x in old})
        self.assertIn(expected_target,{x['address'] for x in new})
        self.assertEqual(len(proofs),expected_count)
        self.assertEqual(proofs[0]['source'],expected_source)
        self.assertEqual(proofs[0]['target'],expected_target)
        self.assertEqual(proofs[0]['pattern'],expected_pattern)
        self.assertEqual(proofs[0]['confidence'],'source_local_constant_candidate_not_executed')
        self.assertEqual(len(newbar),len(oldbar)-expected_count)
        self.assertTrue(any(e['source']==expected_source and e['target']==expected_target and e['evidence']=='recovered_local_constant' for e in edges))
        for p in proofs[0]['support']:
            addr=p['address'];ins=next(engine.disasm(data[addr-base:],addr))
            self.assertEqual(p['sha256'],hashlib.sha256(ins.bytes).hexdigest())
        return old,new

    def test_m68k_pc_relative_jump_exposes_valid_code(self):
        buf=bytearray(32);buf[:4]=m68k(0x4efa,0x000e);buf[16:18]=m68k(0x4e75)
        self.check('m68k',bytes(buf),0,0,0,16,'m68k_pc_relative_d16',1)

    def test_m68k_pc_relative_call_creates_real_static_candidate(self):
        # Distinguish code recovery from simply adding a branch edge to an
        # already known function; source-hashed JSR target is newly reachable.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);buf=bytearray(32)
            buf[0:4]=m68k(0x4eba,0x000e) # JSR d16(PC) => 0x10
            buf[4:6]=m68k(0x4e75);buf[16:18]=m68k(0x4e75)
            source=p/'synthetic.bin';source.write_bytes(buf)
            with patch('scan_graph.make_capstone',side_effect=lambda *_:Engine('m68k')):
                out=benchmark(source,p/'output',fmt='raw',isa='m68k',endian='big',base=0,entry=0)
            self.assertEqual(out['delta']['function_candidates'],1)
            self.assertEqual(out['delta']['resolved_local_constant_edges'],1)
            doc=json.loads((p/'output'/'recovery-queue.json').read_text())
            self.assertEqual(doc['entries'][0]['kind'],'direct_call')
            self.assertEqual(doc['entries'][0]['next_action'],
                             'INDEPENDENT_ANALYZER_OR_RUNTIME_CONFIRMATION_REQUIRED')
            flowfile=p/'output'/'recovered'/'flow-evidence.json'
            tampered=json.loads(flowfile.read_text())
            tampered['indirect_recovery']['local_constant_edges'][0]['support'][0]['sha256']='0'*64
            changed=p/'tampered.json';changed.write_text(json.dumps(tampered))
            con=connect(p/'output'/'benchmark.sqlite')
            try:
                with self.assertRaisesRegex(ValueError,'source hash mismatch'):
                    import_flow(con,changed)
            finally:con.close()

    def test_m68k_immediate_register_jump(self):
        buf=bytearray(32);buf[:8]=m68k(0x207c,0x0000,0x0012,0x4ed0);buf[18:20]=m68k(0x4e75)
        self.check('m68k',bytes(buf),0,0,6,18,'m68k_movea_immediate',1)

    def test_mips_lui_ori_register_jump_exposes_valid_code(self):
        base=0x10000;buf=bytearray(64)
        buf[0:16]=mips(0x3c080001,0x35080020,0x01000008,0)
        buf[32:40]=mips(0x03e00008,0)
        self.check('mips',bytes(buf),base,base,base+8,base+32,'mips_lui_ori',1)

    def test_mips_ambiguous_branch_join_does_not_guess(self):
        # Conditional direct branch reaches the JR without running the LUI/ORI.
        base=0x10000;buf=bytearray(64)
        buf[:20]=mips(0x10000002,0,0x3c080001,0x35080020,0x01000008)
        buf[20:24]=mips(0)
        buf[32:40]=mips(0x03e00008,0)
        image=Image('raw','mips','little',base,base+64,0,base,4,bytes(buf),())
        proofs=[];old,_,_=discover(image,Engine('mips'),100)
        new,_,_=discover(image,Engine('mips'),100,(),True,proofs)
        self.assertEqual(proofs,[])
        self.assertEqual({x['address'] for x in old},{x['address'] for x in new})

    def test_unmapped_target_never_resolves(self):
        buf=bytearray(16);buf[:4]=m68k(0x4efa,0x7000)
        image=Image('raw','m68k','big',0,16,0,0,2,bytes(buf),())
        proof=[];_,_,barriers=discover(image,Engine('m68k'),100,(),True,proof)
        self.assertEqual(proof,[]);self.assertTrue(barriers)

    def test_clean_db_and_benchmark_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);blob=bytearray(32);blob[:4]=m68k(0x4efa,0x000e);blob[16:18]=m68k(0x4e75)
            (p/'owned.bin').write_bytes(blob)
            with patch('scan_graph.make_capstone',side_effect=lambda *_:Engine('m68k')):
                out=benchmark(p/'owned.bin',p/'benchmark',fmt='raw',isa='m68k',endian='big',base=0,entry=0)
            self.assertEqual(out['delta']['instructions'],1)
            self.assertEqual(out['delta']['resolved_local_constant_edges'],1)
            self.assertLess(out['delta']['unresolved_barriers'],0)
            con=connect(p/'benchmark'/'benchmark.sqlite',readonly=True)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM graph_transfers WHERE evidence='recovered_local_constant'").fetchone()[0],1)
            con.close()
            self.assertEqual(out['source_sha256'],hashlib.sha256(blob).hexdigest())
            with self.assertRaises(ValueError):
                with patch('scan_graph.make_capstone',side_effect=lambda *_:Engine('m68k')):
                    benchmark(p/'owned.bin',p/'other',fmt='raw',isa='m68k',endian='big',base=0,entry=0,expected_sha256='0'*64)
            with self.assertRaises(ValueError):
                with patch('scan_graph.make_capstone',side_effect=lambda *_:Engine('m68k')):
                    benchmark(p/'owned.bin',p/'benchmark',fmt='raw',isa='m68k',endian='big',base=0,entry=0)

if __name__=='__main__':unittest.main()
