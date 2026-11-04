"""Compiled regression for SMS Pause/Start NMI and deterministic replay timing."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CPP=r'''
#include "nativepilot/live_sms.hpp"
#include "hardware/continuous.hpp"
#include <cassert>
#include <vector>
#include <iostream>
bool execute_native_instruction(rd::State& s){
 s.pc=std::uint16_t(s.pc+1);s.last_instruction_cycles=4;return true;
}
int main(){
 using namespace recomp;
 {rd::State s;
  s.pc=0x1234;s.set_register(68,2,0xd000);s.iff1=true;
  s.apply_host_input(hw::button::A);
  assert(s.in(0xdc)==0xef && !s.service_pending_console_nmi());
  s.apply_host_input(hw::button::Start|hw::button::A);
  assert(s.pending_console_nmi);
  assert(s.in(0xdc)==0xef); // Start is not a controller port bit
  assert(s.service_pending_console_nmi());
  assert(s.pc==0x66 && s.nmi_events==1 && s.tstates==11);
  assert(s.get_register(68,2)==0xcffe && s.memory(0xcffe,2)==0x1234);
  assert(!s.iff1 && s.iff2); // NMI preserves former IFF1 in IFF2
  s.apply_host_input(hw::button::Start);s.apply_host_input(hw::button::Start);
  assert(!s.service_pending_console_nmi() && s.nmi_events==1);
  s.apply_host_input(0);assert(!s.service_pending_console_nmi());
  s.apply_host_input(hw::button::Start);
  assert(s.service_pending_console_nmi() && s.nmi_events==2);
  assert(!s.service_pending_console_nmi());
 }
 {guest::SmsNativeMachine m;
  std::vector<std::uint8_t> rom(65536);m.load_rom(rom);
  m.state().set_register(68,2,0xd000);
  hw::Runtime runtime(3579545,60,44100);runtime.input(m);
  runtime.record_input(0,{0,0,0,0});
  runtime.record_input(60000,{0,hw::button::Start,0,0});
  runtime.record_input(71000,{0,hw::button::Start,0,0});
  runtime.record_input(75000,{0,0,0,0});
  hw::ContinuousSession session(m,runtime);
  hw::RunLimits l;l.max_frames=3;l.max_steps=200000;l.max_guest_cycles=1000000;
  auto result=session.run(l);
  assert(result.status=="FRAME_BUDGET_REACHED");
  assert(result.frames==3);
  assert(m.state().nmi_events==1);
  assert(m.state().tstates==runtime.cycles()); // no out-of-band input cycles
 }
 std::cout<<"SMS_PAUSE_NMI_V0441_PASS\n";
}
'''
class CompiledPauseNmiTests(unittest.TestCase):
 def test_compiled_pause_nmi_edge_and_session(self):
  if not shutil.which('cmake'):self.skipTest('CMake unavailable')
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'test.cpp';source.write_text(CPP)
   (Path(td)/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.17)\nproject(SmsPauseNmiTest LANGUAGES CXX)\nadd_executable(sms_pause_nmi test.cpp "REPLACE_SOURCE")\ntarget_compile_features(sms_pause_nmi PRIVATE cxx_std_17)\ntarget_include_directories(sms_pause_nmi PRIVATE "REPLACE_ROOT" "REPLACE_SOURCE_PARENT" "REPLACE_PILOT")\n'.replace('REPLACE_SOURCE',str(ROOT/'systems/mastersystem/runtime.cpp').replace('\\','/')).replace('REPLACE_ROOT',str(ROOT).replace('\\','/')).replace('REPLACE_SOURCE_PARENT',str(ROOT/'systems/mastersystem').replace('\\','/')).replace('REPLACE_PILOT',str(ROOT/'nativepilot').replace('\\','/')))
   for args in (['cmake','-S',str(td),'-B',str(Path(td)/'build')],['cmake','--build',str(Path(td)/'build'),'--config','Release']):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
    self.assertEqual(p.returncode,0,p.stdout[-4000:])
   exe=next((p for p in ((Path(td)/'build'/'Release'/'sms_pause_nmi.exe'),(Path(td)/'build'/'sms_pause_nmi.exe'),(Path(td)/'build'/'sms_pause_nmi')) if p.is_file()),None)
   self.assertIsNotNone(exe,'CMake native fixture missing')
   p=subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
   self.assertEqual(p.returncode,0,p.stdout[-4000:])
   self.assertIn('SMS_PAUSE_NMI_V0441_PASS',p.stdout)
 def test_no_title_game_special_case(self):
  data=(ROOT/'systems/mastersystem/runtime.cpp').read_text().lower()
  self.assertNotIn('r-type',data)
  self.assertNotIn('shinobi',data)
  self.assertIn('service_pending_console_nmi',data)
if __name__=='__main__':unittest.main()
