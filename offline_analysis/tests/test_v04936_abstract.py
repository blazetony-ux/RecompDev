#!/usr/bin/env python3
"""CPU-neutral abstract-state engine, with ISA-specific independent fixtures.

No ROM licensing, game launch, emulator, native executable or runtime fallback.
All fixtures contain deliberately authored instruction bytes.
"""
from __future__ import annotations
import json,sys,tempfile,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.engine import interrogate

class CrossIsa(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='recompdev-v36-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def sms(self):
        data=bytearray(b'\xff'*(4*0x4000))
        data[0x7ff0:0x7ff8]=b'TMR SEGA'
        data[:3]=bytes.fromhex('c3 00 01')
        data[0x38]=data[0x66]=0xc9
        return data
    def md(self):
        data=bytearray(0x1000)
        data[:4]=(0xfff000).to_bytes(4,'big')
        data[4:8]=(0x200).to_bytes(4,'big')
        data[0x100:0x104]=b'SEGA'
        return data
    def psx(self):
        data=bytearray(0x800+0x100)
        data[:8]=b'PS-X EXE'
        for offset,value in ((0x10,0x80010000),(0x18,0x80010000),(0x1c,0x100)):
            data[offset:offset+4]=value.to_bytes(4,'little')
        return data
    def scan(self,data):
        rom=self.root/'fixture.bin';rom.write_bytes(data)
        out=self.root/'evidence'
        r=interrogate(rom,out,budget=3000)
        return r,json.loads((out/'instructions.json').read_text()),json.loads((out/'unresolved.json').read_text()),out
    @staticmethod
    def pcs(ins):return {x['pc'] for x in ins}
    def test_z80_ld_hl_jp_hl_constant(self):
        a=self.sms();a[0x100:0x106]=bytes.fromhex('21 20 01 e9 00 00')
        a[0x120:0x122]=bytes.fromhex('18 fe')
        r,ins,gaps,_=self.scan(a)
        self.assertIn(0x120,self.pcs(ins))
        self.assertEqual(r['abstract_execution']['resolved_indirect_sites'],1)
        self.assertNotIn('INDIRECT_TARGET_UNRESOLVED',[x['reason'] for x in gaps])
    def test_z80_unknown_hl_jp_must_not_invent_target(self):
        a=self.sms();a[0x100]=0xe9
        r,ins,gaps,_=self.scan(a)
        self.assertIn('INDIRECT_TARGET_UNRESOLVED',[x['reason'] for x in gaps])
        self.assertEqual(r['abstract_execution']['resolved_indirect_sites'],0)
    def test_z80_stack_matched_call_ret(self):
        a=self.sms()
        a[0x100:0x109]=bytes.fromhex('31 00 d0 cd 20 01 18 fe 00')
        a[0x120:0x122]=bytes.fromhex('00 c9')
        r,ins,gaps,_=self.scan(a)
        self.assertIn(0x120,self.pcs(ins))
        self.assertGreaterEqual(r['abstract_execution']['resolved_return_sites'],1)
        self.assertTrue(any(x['seed']=='matched-call-return' for x in ins))
        self.assertFalse(r['whole_game_code_coverage_qualified'])
    def test_z80_known_hl_indirect_mapper_write(self):
        a=self.sms();a[0x100:0x109]=bytes.fromhex('21 fe ff 36 03 c3 00 40 00')
        a[3*0x4000:3*0x4000+2]=bytes.fromhex('18 fe')
        r,ins,gaps,_=self.scan(a)
        self.assertTrue(any(x['physical']==3*0x4000 for x in ins))
        self.assertNotIn('BANK_REGISTER_VALUE_UNRESOLVED',[x['reason'] for x in gaps])
    def test_z80_unknown_mapper_write_invalidates(self):
        a=self.sms();a[0x100:0x106]=bytes.fromhex('21 fe ff 77 e9 00')
        _,_,gaps,_=self.scan(a)
        self.assertIn('BANK_REGISTER_VALUE_UNRESOLVED',[x['reason'] for x in gaps])
    def test_m68k_lea_register_jump(self):
        a=self.md();a[0x200:0x208]=bytes.fromhex('41 f9 00 00 02 20 4e d0')
        a[0x220:0x224]=bytes.fromhex('4e 71 60 fc')
        r,ins,gaps,_=self.scan(a)
        self.assertIn(0x220,self.pcs(ins))
        self.assertEqual(r['abstract_execution']['resolved_indirect_sites'],1)
    def test_m68k_call_return_context(self):
        a=self.md();a[0x200:0x208]=bytes.fromhex('4e b9 00 00 02 20 60 fe')
        a[0x220:0x222]=bytes.fromhex('4e 75')
        r,ins,gaps,_=self.scan(a)
        self.assertGreaterEqual(r['abstract_execution']['resolved_return_sites'],1)
        self.assertIn(0x206,self.pcs(ins))
    def test_m68k_variable_length_unknown_still_fail_closed(self):
        a=self.md();a[0x200:0x202]=bytes.fromhex('48 e7')
        _,ins,gaps,_=self.scan(a)
        self.assertNotIn(0x200,self.pcs(ins))
        self.assertIn('M68000_INSTRUCTION_LENGTH_UNVERIFIED',[x['reason'] for x in gaps])
    def test_mips_lui_ori_register_indirect(self):
        a=self.psx()
        for off,word in ((0x800,0x3c088001),(0x804,0x35080020),
                         (0x808,0x01000008),(0x80c,0x00000000),
                         (0x820,0x08004008),(0x824,0x00000000)):
            a[off:off+4]=word.to_bytes(4,'little')
        r,ins,gaps,_=self.scan(a)
        self.assertIn(0x80010020,self.pcs(ins))
        self.assertEqual(r['abstract_execution']['resolved_indirect_sites'],1)
        self.assertGreaterEqual(r['abstract_execution']['delay_slots_decoded'],2)
    def test_mips_target_resolved_before_slot_clobber(self):
        a=self.psx()
        for off,word in ((0x800,0x3c088001),(0x804,0x35080020),
                         (0x808,0x01000008),(0x80c,0x3c089000),
                         (0x820,0x08004008),(0x824,0x00000000)):
            a[off:off+4]=word.to_bytes(4,'little')
        r,ins,gaps,_=self.scan(a)
        self.assertIn(0x80010020,self.pcs(ins))
        self.assertNotIn('INDIRECT_TARGET_UNRESOLVED',[x['reason'] for x in gaps])
    def test_mips_jal_jr_ra_matched_return(self):
        a=self.psx()
        for off,word in ((0x800,0x0c004008),(0x804,0x00000000),
                         (0x808,0x08004002),(0x80c,0x00000000),
                         (0x820,0x03e00008),(0x824,0x00000000)):
            a[off:off+4]=word.to_bytes(4,'little')
        r,ins,gaps,_=self.scan(a)
        self.assertGreaterEqual(r['abstract_execution']['resolved_return_sites'],1)
        self.assertEqual(r['abstract_execution']['provider_abstract_state_abi'],2)
        self.assertTrue(any(x['pc']==0x80010008 for x in ins))
    def test_speculative_call_continuation_explicit(self):
        a=self.sms();a[0x100:0x106]=bytes.fromhex('cd 20 01 18 fe 00')
        a[0x120:0x123]=bytes.fromhex('3e 01 76') # callee never returns
        r,ins,_,out=self.scan(a)
        self.assertGreater(r['abstract_execution']['speculative_instruction_candidates'],0)
        self.assertTrue(any(x['classification'].startswith('SPECULATIVE') for x in ins))
        self.assertFalse(r['semantic_parity_qualified'])
        for item in r['artifacts'].values():
            self.assertEqual(hashlib.sha256((out/item['file']).read_bytes()).hexdigest(),item['sha256'])
    def test_z80_mapper_control_write_not_treated_as_rom_mapping(self):
        a=self.sms();a[0x100:0x108]=bytes.fromhex('3e 01 32 fc ff c3 00 40')
        _,ins,gaps,_=self.scan(a)
        reasons=[x['reason'] for x in gaps]
        self.assertIn('MAPPER_CONTROL_WRITE_INVALIDATES_ROM_WINDOW',reasons)
        self.assertIn('ROM_BANK_CONTEXT_UNRESOLVED',reasons)
    def test_z80_known_indexed_write_safe_range_preserves_mapping(self):
        a=self.sms();a[0x100:0x10b]=bytes.fromhex('dd 21 00 ff dd 36 fc 01 c3 00 40')
        _,_,gaps,_=self.scan(a)
        self.assertNotIn('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER',[x['reason'] for x in gaps])
    def test_mips_reserved_lui_not_falsely_const_folded(self):
        a=self.psx();a[0x800:0x804]=(0x3c288001).to_bytes(4,'little')
        _,ins,gaps,_=self.scan(a)
        self.assertIn('UNSUPPORTED_MIPS_RESERVED_LUI_ENCODING',[x['reason'] for x in gaps])
        self.assertNotIn(0x80010000,self.pcs(ins))
    def test_recursive_call_depth_bounded(self):
        a=self.sms();a[0x100:0x103]=bytes.fromhex('cd 00 01')
        r,_,gaps,_=self.scan(a)
        self.assertIn('RETURN_STACK_BOUND_EXCEEDED',[x['reason'] for x in gaps])
        self.assertLessEqual(r['abstract_execution']['abstract_contexts_visited'],3000)

if __name__=='__main__':unittest.main(verbosity=2)
