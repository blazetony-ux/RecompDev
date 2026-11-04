"""Compiled SMS I/O tests anchored by independent port reads, no game-specific code."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CXX=r'''
#include "systems/mastersystem/runtime.hpp"
#include <cassert>
#include <cstdio>
int main(){
  rd::State s; s.apply_host_input(0);
  s.out(0x3f,0xf5);assert(s.in(0xdd)==0xff);
  s.out(0x3f,0x55);assert(s.in(0xdd)==0x3f);
  s.out(0x3f,0xff);assert(s.in(0xdd)==0xff);
  // Both lines are input-controlled when set as inputs; neutral pads read high.
  s.out(0x3f,0xff); assert(s.in(0xdd)==0xff);
  std::puts("SMS_TH_FEEDBACK_COMPILED_PASS");
}
'''
class SmsThFeedbackDev(unittest.TestCase):
 def test_compiled_th_feedback(self):
  self.assertTrue(shutil.which('cmake'))
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'main.cpp').write_text(CXX)
   (p/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(sms_th LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nadd_executable(sms_th main.cpp "'+str(ROOT/'systems/mastersystem/runtime.cpp').replace('\\','/')+'")\ntarget_include_directories(sms_th PRIVATE "'+str(ROOT).replace('\\','/')+'")\n')
   for cmd in [['cmake','-S',str(p),'-B',str(p/'build')],['cmake','--build',str(p/'build'),'--config','Release']]:
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
    self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   exe=next(x for x in (p/'build').rglob('sms_th.exe' if os.name=='nt' else 'sms_th') if x.is_file())
   r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   self.assertIn('SMS_TH_FEEDBACK_COMPILED_PASS',r.stdout)
if __name__=='__main__':unittest.main()
