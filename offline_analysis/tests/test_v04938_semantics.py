#!/usr/bin/env python3
"""Independent Z80, 68000, MIPS fixtures for CPU fact precision and safety.

Every test image is independently authored and has no external game bytes.
"""
from __future__ import annotations
import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.model import AbstractFacts,Instruction,Unresolved
from offline_analysis.engine import interrogate
from offline_analysis.plugins import cpu_z80,cpu_m68k,cpu_mips

class Semantics(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory(prefix='rd-v38-semantics-')
        self.addCleanup(d.cleanup)
        self.home=Path(d.name)
    def z(self,raw):return cpu_z80.decode(lambda pc,n:raw[pc:pc+n],0)
    def test_z80_interrupt_mode_preserves_stack_and_registers(self):
        before=AbstractFacts((('A',4),('SP',0xdf00),('DE',0x1234),('HL',0x4010)))
        for op in (0x46,0x56,0x5e,0x66,0x76,0x7e,0x47):
            with self.subTest(op=op):
                self.assertEqual(dict(cpu_z80.advance(self.z(bytes((0xed,op))),before).pairs),dict(before.pairs))
    def test_z80_word_add_is_exact_or_unknown(self):
        state=AbstractFacts((('HL',0xffff),('DE',2)))
        self.assertEqual(cpu_z80.advance(self.z(b'\x19'),state).get('HL'),1)
        self.assertIsNone(cpu_z80.advance(self.z(b'\x19'),AbstractFacts((('HL',8),))).get('HL'))
    def test_z80_two_half_immediates_reconstruct_pair(self):
        state=AbstractFacts()
        for bytes_ in (b'\x06\x16',b'\x0e\xbf'):
            state=cpu_z80.advance(self.z(bytes_),state)
        self.assertEqual(state.get('BC'),0x16bf)
        state=cpu_z80.advance(self.z(b'\x0d'),state)
        self.assertEqual(state.get('BC'),0x16be)
        state=cpu_z80.advance(self.z(b'\x78'),state)
        self.assertEqual(state.get('A'),0x16)
    def test_z80_cb_bit_and_partial_update(self):
        before=AbstractFacts((('HL',0xfffc),('SP',0xd000)))
        ins=self.z(bytes.fromhex('cb 46'))
        self.assertEqual(cpu_z80.advance(ins,before),before)
        self.assertNotIn('unknown_memory_write',ins.effects)
        rotate=self.z(bytes.fromhex('cb 04'))
        self.assertIsNone(cpu_z80.advance(rotate,before).get('HL'))
        self.assertEqual(cpu_z80.advance(rotate,before).get('SP'),0xd000)
    def test_z80_ed_io_repeat_preserves_stack_while_advancing_hl(self):
        state=AbstractFacts((('HL',0xc100),('SP',0xdffe),('B',4),('C',0xbf),('BC',0x04bf)))
        op=self.z(bytes.fromhex('ed b3'))
        self.assertEqual(op.effects.get('io_block'),(1,True))
        self.assertNotIn('unknown_memory_write',op.effects)
        after=cpu_z80.advance(op,state)
        self.assertEqual(after.get('SP'),0xdffe)
        self.assertEqual(after.get('HL'),0xc104)
        self.assertEqual(after.get('BC'),0xbf)
    def test_z80_repeat_input_known_destination_can_overlap_mapper(self):
        from offline_analysis.plugins.machine_sms import transition,initial
        from offline_analysis.model import Image,Seed
        im=Image('sega-master-system','z80','sms-banked',(Seed(0,'reset'),),0,0x10000,bank_bytes=0x4000)
        op=self.z(bytes.fromhex('ed b2'))
        state=AbstractFacts((('HL',0xfffc),('B',4)))
        _,warnings=transition(im,op,initial(im),state)
        self.assertIn('MAPPER_CONTROL_WRITE_INVALIDATES_ROM_WINDOW',warnings)
    def test_z80_unknown_ed_fails_closed(self):
        with self.assertRaisesRegex(Unresolved,'Z80_ED_SEMANTICS_UNQUALIFIED'):
            self.z(bytes.fromhex('ed b1'))
    def test_z80_startup_fixture_discovers_safe_bank_after_io(self):
        code=bytearray(b'\xff'*(4*0x4000))
        code[0x7ff0:0x7ff8]=b'TMR SEGA';code[0x38]=code[0x66]=0xc9
        code[:3]=bytes.fromhex('c3 00 01')
        payload=bytes.fromhex('31 fe df ed 56 06 02 0e 10 21 00 c0 11 01 00 19 ed b3 3e 03 32 fe ff c3 00 40')
        code[0x100:0x100+len(payload)]=payload
        code[3*0x4000:3*0x4000+2]=bytes.fromhex('18 fe')
        src=self.home/'game.sms';src.write_bytes(code)
        out=self.home/'report';r=interrogate(src,out,budget=2000)
        rows=json.loads((out/'instructions.json').read_text())
        self.assertTrue(any(row['physical']==3*0x4000 for row in rows))
        self.assertGreaterEqual(r['decoded_candidates'],12)
    def test_m68k_pc_lea_addq_and_address_register_copy(self):
        state=AbstractFacts((('A7',0xfff000),))
        lea=cpu_m68k.decode(lambda pc,n:bytes.fromhex('41 fa 00 0e')[pc:pc+n],0x0)
        state=cpu_m68k.advance(lea,state)
        self.assertEqual(state.get('A0'),0x10)
        add=cpu_m68k.decode(lambda pc,n:b'\x52\x88'[pc:pc+n],0)
        state=cpu_m68k.advance(add,state)
        self.assertEqual(state.get('A0'),0x11)
        copy=cpu_m68k.decode(lambda pc,n:b'\x43\xd0'[pc:pc+n],0)
        self.assertEqual(cpu_m68k.advance(copy,state).get('A1'),0x11)
    def test_m68k_movea_sign_extension(self):
        inst=cpu_m68k.decode(lambda pc,n:bytes.fromhex('30 7c ff 80')[pc:pc+n],0)
        self.assertEqual(cpu_m68k.advance(inst,AbstractFacts()).get('A0'),0xffffff80)
    def test_mips_unsigned_alu_and_variable_shift(self):
        state=AbstractFacts((('R0',0),('R8',0x80000000),('R9',1)))
        addu=(9<<21)|(8<<16)|(10<<11)|35
        sub=cpu_mips.decode(lambda pc,n:addu.to_bytes(4,'little')[pc:pc+n],0)
        self.assertEqual(cpu_mips.advance(sub,state).get('R10'),0x80000001)
        shift=(9<<21)|(8<<16)|(11<<11)|6
        ins=cpu_mips.decode(lambda pc,n:shift.to_bytes(4,'little')[pc:pc+n],0)
        self.assertEqual(cpu_mips.advance(ins,state).get('R11'),0x40000000)
    def test_mips_signed_addi_overflow_blocks_analysis(self):
        state=AbstractFacts((('R0',0),('R8',0x7fffffff)))
        opcode=(8<<26)|(8<<21)|(9<<16)|1
        ins=cpu_mips.decode(lambda pc,n:opcode.to_bytes(4,'little')[pc:pc+n],0)
        with self.assertRaisesRegex(Unresolved,'MIPS_ADDI_OVERFLOW'):
            cpu_mips.advance(ins,state)
        with self.assertRaisesRegex(Unresolved,'MIPS_ADDI_POSSIBLE'):
            cpu_mips.advance(ins,AbstractFacts((('R0',0),)))

if __name__=='__main__':unittest.main(verbosity=2)
