"""Compile real generated-runtime arithmetic-right-shift semantics on the host C++ compiler."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CPP=r'''
#include "systems/mastersystem/runtime.hpp"
#include <cassert>
#include <cstdio>
int main(){
 using rd::evaluate;using rd::Op;
 assert(evaluate(Op::INT_SRIGHT,0x81,1,1,1,1)==0xc0);
 assert(evaluate(Op::INT_SRIGHT,0x7f,1,1,1,1)==0x3f);
 assert(evaluate(Op::INT_SRIGHT,0x80,7,1,1,1)==0xff);
 assert(evaluate(Op::INT_SRIGHT,0x80,8,1,1,1)==0xff);
 assert(evaluate(Op::INT_SRIGHT,0x80,64,1,1,1)==0xff);
 assert(evaluate(Op::INT_SRIGHT,0x7f,100,1,1,1)==0);
 assert(evaluate(Op::INT_SRIGHT,0x8000,1,2,2,1)==0xc000);
 assert(evaluate(Op::INT_SRIGHT,0x80000000u,8,4,4,1)==0xff800000u);
 assert(evaluate(Op::INT_SRIGHT,0x8000000000000000ull,1,8,8,1)==0xc000000000000000ull);
 assert(evaluate(Op::INT_RIGHT,0x81,1,1,1,1)==0x40);
 std::puts("SIGNED_RIGHT_SHIFT_COMPILED_PASS");
}'''
class RightShiftSemantics(unittest.TestCase):
 def test_compiled_shift_cases(self):
  self.assertIsNotNone(shutil.which('cmake'),'CMake is required for mandatory native semantics tests')
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'test.cpp').write_text(CPP)
   (p/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.17)\nproject(shift_semantics LANGUAGES CXX)\nadd_executable(shift_semantics test.cpp "'+str(ROOT/'systems/mastersystem/runtime.cpp').replace('\\','/')+'")\ntarget_compile_features(shift_semantics PRIVATE cxx_std_17)\ntarget_include_directories(shift_semantics PRIVATE "'+str(ROOT).replace('\\','/')+'")\n')
   for cmd in (['cmake','-S',str(p),'-B',str(p/'build')],['cmake','--build',str(p/'build'),'--config','Release']):
    result=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   exe=next(x for x in (p/'build').rglob('shift_semantics.exe' if os.name=='nt' else 'shift_semantics') if x.is_file())
   result=subprocess.run([str(exe)],text=True,capture_output=True,timeout=20)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   self.assertIn('SIGNED_RIGHT_SHIFT_COMPILED_PASS',result.stdout)
if __name__=='__main__':unittest.main()
