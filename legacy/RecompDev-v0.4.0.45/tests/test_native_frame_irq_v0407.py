"""Synthetic native C++/SMS VBlank and IRQ tests; not Shinobi reference parity."""
import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from nativepilot.generator import generate_project,sha256
ROOT=Path(__file__).resolve().parents[1]
def v(space,offset,size=1):return {'space':space,'offset':offset,'size':size}
@unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),'native compiler required')
class FrameIRQTests(unittest.TestCase):
 def test_interrupt_enabled_native_wait_released_only_by_generated_handler(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=bytearray(65536)
   parts={
    0:(b'\xc3\x00\x01','JP',None,[{'op':'BRANCH','inputs':[v('ram',0x100)]}]),
    0x38:(b'\x3e\x01','LD',0x3a,[{'op':'COPY','output':v('register',1),'inputs':[v('const',1)]}]),
    0x3a:(b'\x32\x01\xc0','LD',0x3d,[{'op':'COPY','output':v('ram',0xc001),'inputs':[v('register',1)]}]),
    0x3d:(b'\xc9','RET',None,[{'op':'LOAD','memory_space':'ram','output':v('register',66,2),'inputs':[v('const',401,8),v('register',68,2)]},{'op':'INT_ADD','output':v('register',68,2),'inputs':[v('register',68,2),v('const',2,2)]},{'op':'RETURN','inputs':[v('register',66,2)]}]),
    0x100:(b'\x31\xfe\xdf','LD',0x103,[{'op':'COPY','output':v('register',68,2),'inputs':[v('const',0xdffe,2)]}]),
    0x103:(b'\x3e\x20','LD',0x105,[{'op':'COPY','output':v('register',1),'inputs':[v('const',0x20)]}]),
    0x105:(b'\xd3\xbf','OUT',0x107,[{'op':'STORE','memory_space':'io','inputs':[v('const',529,8),v('const',0xbf,2),v('register',1)]}]),
    0x107:(b'\x3e\x81','LD',0x109,[{'op':'COPY','output':v('register',1),'inputs':[v('const',0x81)]}]),
    0x109:(b'\xd3\xbf','OUT',0x10b,[{'op':'STORE','memory_space':'io','inputs':[v('const',529,8),v('const',0xbf,2),v('register',1)]}]),
    0x10b:(b'\xfb','EI',0x10c,[{'op':'CALLOTHER','inputs':[v('const',5,4)]}]),
    0x10c:(b'\x3a\x01\xc0','LD',0x10f,[{'op':'COPY','output':v('register',1),'inputs':[v('ram',0xc001)]}]),
    0x10f:(b'\xb7','OR',0x110,[{'op':'INT_EQUAL','output':v('unique',100),'inputs':[v('register',1),v('const',0)]}]),
    0x110:(b'\x28\xfa','JR',0x112,[{'op':'CBRANCH','inputs':[v('ram',0x10c),v('unique',100)]}]),
    0x112:(b'\x76','HALT',None,[{'op':'CALLOTHER','inputs':[v('const',9,4)]}]),
   }
   ins=[]
   for pc,(code,mnemonic,fall,ops) in parts.items():
    source[pc:pc+len(code)]=code
    ins.append({'address':pc,'length':len(code),'bytes_sha256':hashlib.sha256(code).hexdigest(),'mnemonic':mnemonic,'fallthrough':fall,'pcode':ops})
   rom=root/'synthetic.sms';rom.write_bytes(source)
   doc={'schema':'recomp-function-pcode-v1','source_sha256':sha256(rom),'target_id':'synthetic-vblank','language':'z80:LE:16:default','functions':[{'entry':0,'instructions':ins}]}
   project=root/'project';generated=generate_project(doc,rom,project)
   self.assertEqual(generated['unsupported_instructions'],0)
   subprocess.run(['cmake','-S',str(project),'-B',str(project/'build')],check=True,capture_output=True)
   subprocess.run(['cmake','--build',str(project/'build'),'--parallel','2'],check=True,capture_output=True)
   proc=subprocess.run([str(project/'build'/'RecompDevNativePilot'),str(rom),'18000'],capture_output=True,text=True,timeout=20,check=True)
   out=json.loads(next(t.split('=',1)[1] for t in proc.stdout.splitlines() if t.startswith('PILOT_RESULT=')))
   self.assertEqual(out['status'],'HALT_AWAITING_INTERRUPT',out)
   self.assertGreater(out['maskable_interrupts'],0)
   self.assertEqual(out['c001_nonzero_writes'],1)
   self.assertGreater(out['c001_reads'],0)
   self.assertEqual(out['last_c001_writer_pc'],0x3a)
   self.assertEqual(out['pc'],0x113)
   self.assertEqual(out['vdp_registers'][1],0x20)
   self.assertTrue(out['clock_model'].endswith('NON_PARITY'))
   self.assertEqual(out['events'][0]['kind'],'VDP_CONTROL_WRITE')
   self.assertEqual(out['events'][0]['address'],0xbf)
   self.assertEqual(out['events'][0]['value'],0x20)
   self.assertEqual(out['events'][1]['value'],0x81)
   self.assertTrue(any(e['kind']=='IRQ' for e in out['events']))
   self.assertFalse(out['events_truncated'])
 def test_vdp_status_ei_latency_and_fail_closed_im2(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d);cpp=path/'unit.cpp';exe=path/'unit'
   cpp.write_text('''#include "runtime.hpp"
#include <cassert>
int main(){rd::State s;s.set_register(68,2,0xdffe);s.pc=0x110;s.vdp_regs[1]=0x20;s.on_ei();s.advance_cycles(228*192);
assert(s.vblank_events==1);assert(!s.service_pending_interrupt());s.end_instruction();assert(!s.service_pending_interrupt());s.end_instruction();assert(s.service_pending_interrupt());
assert(s.pc==0x38);assert(s.maskable_interrupts==1);assert(s.memory(s.get_register(68,2),2)==0x110);
assert(s.in(0xbf)&0x80);assert(!(s.vdp_status&0x80));
rd::State t;t.set_register(68,2,0xdffe);t.vdp_regs[1]=0x20;t.iff1=true;t.interrupt_mode=2;t.advance_cycles(228*192);assert(!t.service_pending_interrupt());assert(t.stopped=="IM2_INTERRUPT_VECTOR_NOT_MODELLED");
rd::State n;n.set_register(68,2,0xdffe);n.pc=0x234;n.iff1=true;n.pulse_nmi();assert(n.pc==0x66 && !n.iff1 && n.iff2 && n.memory(n.get_register(68,2),2)==0x234);}
''')
   subprocess.run(['g++','-std=c++17','-I',str(ROOT/'nativepilot'),str(cpp),str(ROOT/'nativepilot/runtime.cpp'),'-o',str(exe)],check=True,capture_output=True)
   subprocess.run([str(exe)],check=True,capture_output=True)
