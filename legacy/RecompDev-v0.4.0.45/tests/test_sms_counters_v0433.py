"""Compiled SMS counter/device tests, independent of commercial ROM binaries."""
import os, subprocess, shutil, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CXX=r'''
#include "systems/mastersystem/runtime.hpp"
#include "systems/mastersystem/counters.hpp"
#include <cassert>
#include <cstdio>
using namespace rd;
int main(){
 State s;
 assert(s.in(0x7e)==0);assert(s.in(0x40)==0);
 s.advance_cycles(228*191);assert(s.in(0x7e)==191);
 s.advance_cycles(228);assert(s.in(0x7e)==192);
 s.advance_cycles(228*26);assert(s.in(0x7e)==218);
 s.advance_cycles(228);assert(s.in(0x7e)==0xd5); // 219: wraps from DA to D5
 s.advance_cycles(228*42);assert(s.in(0x7e)==0xff);
 s.advance_cycles(228);assert(s.in(0x7e)==0);assert(s.frames==1);
 s.advance_cycles(228*77);assert(s.in(0x7e)==77);
 assert(s.vcounter_reads==9);
 assert(s.in(0x7f)==0&&s.in(0x41)==0);assert(s.hcounter_reads==2);
 s.out(0x3f,0x00);s.advance_cycles(200);s.out(0x3f,0x22);
 assert(s.hcounter_latches==1);auto held=s.in(0x7f);
 s.advance_cycles(228);assert(s.in(0x7f)==held); // latch does not free-run
 assert(s.in(0xdc)==0xff);s.apply_host_input(16);assert(s.in(0xdc)!=0xff);
 assert(recomp::sms::vcounter_pal_192(243)==0xba);
 assert(recomp::sms::vcounter_pal_192(312)==0xff);
 std::puts("SMS_COUNTERS_COMPILED_PASS");
}
'''
class SmsCounterTests(unittest.TestCase):
 def test_compiled_counter_and_controller_ports(self):
  self.assertTrue(shutil.which('cmake'),'CMake required for real compiled gate')
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'main.cpp').write_text(CXX)
   (p/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(smscounter LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nadd_executable(smscounter main.cpp "'+str((ROOT/'systems/mastersystem/runtime.cpp')).replace('\\','/')+'")\ntarget_include_directories(smscounter PRIVATE "'+str(ROOT).replace('\\','/')+'")\n')
   c=subprocess.run(['cmake','-S',str(p),'-B',str(p/'build')],capture_output=True,text=True,timeout=60)
   self.assertEqual(c.returncode,0,c.stdout+c.stderr)
   b=subprocess.run(['cmake','--build',str(p/'build'),'--config','Release'],capture_output=True,text=True,timeout=120)
   self.assertEqual(b.returncode,0,b.stdout+b.stderr)
   exe=next(x for x in (p/'build').rglob('smscounter.exe' if os.name=='nt' else 'smscounter') if x.is_file())
   r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   self.assertIn('SMS_COUNTERS_COMPILED_PASS',r.stdout)
 def test_no_game_specific_conditionals(self):
  code=(ROOT/'systems/mastersystem/runtime.cpp').read_text()
  self.assertNotIn('shinobi',code.lower())
  self.assertIn('vcounter_ntsc_192',code)
if __name__=='__main__':unittest.main()
