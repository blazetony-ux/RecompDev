#!/usr/bin/env python3
"""v37 CPU/machine-neutral memory effects and dataflow join tests."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from offline_analysis.engine import interrogate,AnalysisFailure
from offline_analysis.model import AbstractFacts,join_facts
from offline_analysis.plugins import cpu_m68k

class MemoryAndFlow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rd-v37-memory-')
        self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name)
    def scan(self,code,*,bank=1,extra=None):
        data=bytearray(b'\xff'*(4*0x4000))
        data[0x7ff0:0x7ff8]=b'TMR SEGA';data[:3]=bytes.fromhex('c3 00 01')
        data[0x38]=data[0x66]=0xc9
        data[0x100:0x100+len(code)]=code
        if extra:
            for addr,chunk in extra.items():data[addr:addr+len(chunk)]=chunk
        source=self.d/'rom.sms';source.write_bytes(data)
        out=self.d/'results'
        result=interrogate(source,out,budget=2000)
        instructions=json.loads((out/'instructions.json').read_text())
        gaps=json.loads((out/'unresolved.json').read_text())
        return result,instructions,gaps
    @staticmethod
    def reasons(gaps):return [x['reason'] for x in gaps]
    def test_known_safe_stack_push_and_return_preserves_rom_bank(self):
        # LD SP,D000; CALL target; JP 4000; RET at target. The write is in RAM.
        code=bytes.fromhex('31 00 d0 cd 20 01 c3 00 40')
        r,ins,gaps=self.scan(code,extra={0x120:b'\xc9',0x4000:b'\x18\xfe'})
        self.assertTrue(any(x['physical']==0x4000 for x in ins))
        self.assertNotIn('STACK_WRITE_MAY_CHANGE_MAPPER',self.reasons(gaps))
    def test_unsafe_stack_wrap_must_invalidate_mapping(self):
        r,ins,gaps=self.scan(bytes.fromhex('31 fd ff cd 20 01 c3 00 40'),extra={0x120:b'\xc9'})
        self.assertIn('STACK_WRITE_MAY_CHANGE_MAPPER',self.reasons(gaps))
        self.assertIn('ROM_BANK_CONTEXT_UNRESOLVED',self.reasons(gaps))
    def test_unknown_stack_keeps_unknown(self):
        r,ins,gaps=self.scan(bytes.fromhex('cd 20 01 c3 00 40'),extra={0x120:b'\xc9'})
        self.assertIn('STACK_WRITE_MAY_CHANGE_MAPPER',self.reasons(gaps))
    def test_counted_ldir_known_safe_destination(self):
        code=bytes.fromhex('21 00 40 11 00 c0 01 08 00 ed b0 c3 00 40')
        r,ins,gaps=self.scan(code,extra={0x4000:b'\x18\xfe'})
        self.assertTrue(any(x['physical']==0x4000 for x in ins))
        self.assertNotIn('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER',self.reasons(gaps))
    def test_ldir_with_unknown_bc_fails_closed(self):
        code=bytes.fromhex('11 00 c0 ed b0 c3 00 40')
        _,_,gaps=self.scan(code)
        self.assertIn('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER',self.reasons(gaps))
    def test_ldir_count_hits_mapper(self):
        code=bytes.fromhex('11 fb ff 01 04 00 ed b0 c3 00 40')
        _,_,gaps=self.scan(code)
        self.assertIn('MAPPER_CONTROL_WRITE_INVALIDATES_ROM_WINDOW',self.reasons(gaps))
    def test_ldir_zero_count_wraps_all_memory(self):
        code=bytes.fromhex('11 00 c0 01 00 00 ed b0 c3 00 40')
        _,_,gaps=self.scan(code)
        self.assertIn('MAPPER_CONTROL_WRITE_INVALIDATES_ROM_WINDOW',self.reasons(gaps))
    def test_index_displacement_known_mapper_register(self):
        code=bytes.fromhex('dd 21 00 00 dd 36 fe 03 c3 00 40')
        r,ins,gaps=self.scan(code,extra={3*0x4000:b'\x18\xfe'})
        self.assertTrue(any(x['physical']==3*0x4000 for x in ins))
        self.assertNotIn('BANK_REGISTER_VALUE_UNRESOLVED',self.reasons(gaps))
    def test_index_unknown_register_must_invalidate(self):
        code=bytes.fromhex('dd 36 fe 03 c3 00 40')
        _,_,gaps=self.scan(code)
        self.assertIn('UNKNOWN_MEMORY_WRITE_MAY_TOUCH_MAPPER',self.reasons(gaps))
    def test_join_drops_conflicting_cpu_facts_never_invents_mapping(self):
        a=AbstractFacts((('A',3),('SP',0xd000),('BC',4)))
        b=AbstractFacts((('A',4),('SP',0xd000),('BC',5)))
        joined=join_facts(a,b)
        self.assertEqual(joined.pairs,(('SP',0xd000),))
    def test_m68k_vector_initial_stack_and_normal_call_adjustments(self):
        from offline_analysis.model import Image,Seed,Instruction
        image=Image('sega-mega-drive','m68000','cartridge-flat',(Seed(0x200,'reset'),),0,4096,details={'initial_sp':0xfff000})
        facts=cpu_m68k.initial(image)
        self.assertEqual(facts.get('A7'),0xfff000)
        call=Instruction(6,'call',0x400,effects={'stack_bytes':-4})
        after=cpu_m68k.advance(call,facts)
        self.assertEqual(after.get('A7'),0xffeffc)
        self.assertEqual(cpu_m68k.advance(Instruction(2,'return',effects={'stack_bytes':4}),after).get('A7'),0xfff000)
    def test_m68k_exception_return_not_a_call_return(self):
        from offline_analysis.model import Unresolved
        with self.assertRaises(Unresolved):cpu_m68k.decode(lambda pc,n:b'\x4e\x73'[:n],0)
    def test_comparison_attests_old_report_before_diff(self):
        r,ins,gaps=self.scan(bytes.fromhex('00 18 fd'))
        source=self.d/'rom.sms'
        old=self.d/'results'
        result=interrogate(source,self.d/'new',budget=2000,compare_to=old)
        self.assertEqual(result['regression_comparison']['new_candidates'],0)
        self.assertEqual(result['regression_comparison']['missing_candidates'],0)
        compare=self.d/'new/regression-comparison.json'
        self.assertEqual(hashlib.sha256(compare.read_bytes()).hexdigest(),result['artifacts']['regression-comparison.json']['sha256'])
        with (old/'instructions.json').open('a') as f:f.write('tamper')
        with self.assertRaisesRegex(AnalysisFailure,'COMPARISON_INSTRUCTION_RECEIPT_TAMPERED'):
            interrogate(source,self.d/'reject',compare_to=old)
        self.assertFalse((self.d/'reject').exists())

if __name__=='__main__':unittest.main(verbosity=2)
