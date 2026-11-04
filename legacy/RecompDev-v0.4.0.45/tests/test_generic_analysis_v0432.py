"""Cross-ISA recovery and independent-reference/triage fail-closed tests."""
import hashlib,json,struct,tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.formats import Image
from scan_graph import discover
from test_cross_isa_recovery_v0430 import Engine
from multisa.checkpoints import compare
from multisa.triage import triage

class GenericRecoveryTests(unittest.TestCase):
    def test_mips_longer_constant_path_resolves(self):
        # LUI t0,1; ORI t0,0x20; NOP; ADDIU t0,t0,0x10; JR t0; NOP;
        base=0x10000
        ints=[0x3c080001,0x35080020,0,0x25080010,0x01000008,0]
        buf=bytearray(80);buf[:24]=struct.pack('<6I',*ints)
        buf[48:56]=struct.pack('<2I',0x03e00008,0)
        image=Image('raw','mips','little',base,base+len(buf),0,base,4,bytes(buf),())
        old,_,_=discover(image,Engine('mips'),100)
        proofs=[];new,_,_=discover(image,Engine('mips'),100,(),True,proofs)
        self.assertNotIn(base+48,{i['address'] for i in old})
        self.assertIn(base+48,{i['address'] for i in new})
        self.assertEqual(proofs[0]['pattern'],'mips_linear_constant_propagation')
        self.assertEqual(proofs[0]['target'],base+48)
        self.assertEqual(len(proofs[0]['support']),4)

    def test_mips_ambiguous_join_rejects_extended_proof(self):
        # Branch into middle of const construction yields independent predecessor.
        base=0x10000;words=[0x10000003,0,0x3c080001,0x35080020,0,0x25080010,0x01000008,0]
        buf=bytearray(80);buf[:len(words)*4]=struct.pack('<8I',*words)
        buf[48:56]=struct.pack('<2I',0x03e00008,0)
        image=Image('raw','mips','little',base,base+len(buf),0,base,4,bytes(buf),())
        proofs=[];discover(image,Engine('mips'),100,(),True,proofs)
        self.assertEqual(proofs,[])

    def test_merged_reference_checkpoint_first_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);sha='a'*64;initial='b'*64
            base={'schema':'recomp-checkpoints-v1','source_sha256':sha,'isa':'future-isa',
                  'initial_state_sha256':initial,'points':[{'seq':0,'pc':4,'registers':{'r0':0}},
                     {'seq':1,'pc':8,'registers':{'r0':1}}]}
            for role in ('reference','candidate'):
                (p/role).write_text(json.dumps({**base,'role':role}))
            a=compare(p/'reference',p/'candidate')
            self.assertEqual(a['status'],'MATCHING_OBSERVED_PREFIX')
            obj=json.loads((p/'candidate').read_text());obj['points'][1]['registers']['r0']=2
            (p/'candidate').write_text(json.dumps(obj))
            b=compare(p/'reference',p/'candidate')
            self.assertEqual(b['first_divergence']['seq'],1)
            self.assertEqual(b['first_divergence']['field'],'registers')
            obj['initial_state_sha256']='0'*64
            (p/'candidate').write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,'unaligned'):
                compare(p/'reference',p/'candidate')

    def test_invalid_and_unaligned_checkpoint_streams_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r={'schema':'recomp-checkpoints-v1','role':'reference','isa':'m68k','source_sha256':'a'*64,'initial_state_sha256':'b'*64,'points':[]}
            (p/'ref').write_text(json.dumps(r))
            (p/'cand').write_text(json.dumps({**r,'role':'candidate'}))
            with self.assertRaisesRegex(ValueError,'empty'):
                compare(p/'ref',p/'cand')
            obj={**r,'role':'candidate','points':[{'seq':2,'pc':8},{'seq':1,'pc':4}]}
            (p/'cand').write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,'monotonically'):
                compare(p/'ref',p/'cand')

    def test_generic_triage_preserves_provenance_and_does_not_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            obj={'schema':'recomp-flow-evidence-v1','source_sha256':'a'*64,'architecture':'brand-new-cpu',
                 'observed_addresses':[4,8], 'barriers':[{'address':4,'reason':'register jump target unknown'},
                 {'address':8,'reason':'invalid MIPS branch delay slot'},
                 {'address':16,'reason':'decoder rejected candidate / unmapped address'}]}
            (p/'flow').write_text(json.dumps(obj))
            out=triage(p/'flow',p/'triage')
            self.assertEqual(out['classes']['INDIRECT_TARGET'],1)
            self.assertEqual(out['classes']['DELAY_SLOT'],1)
            self.assertEqual(out['barrier_count'],3)
            self.assertEqual(out['queue'][2]['priority'],'POTENTIAL_UNREACHABLE')
            self.assertEqual(out['qualification'],'NO_AUTOMATIC_NATIVE_PROMOTION')
            self.assertEqual(out,json.loads((p/'triage').read_text()))

if __name__=='__main__':unittest.main()
