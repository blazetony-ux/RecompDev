"""Generic conditional Z80 CALL/RET must guard stack side effects in P-code lowering."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from nativepilot.generator import emit_instruction
ROOT = Path(__file__).resolve().parents[1]

def v(space,offset,size=1):return dict(space=space,offset=offset,size=size)
def op(code,inputs,output=None,space=None):
 return dict(op=code,inputs=inputs,output=output,memory_space=space)

def conditional(pc,kind):
 fall=pc+(3 if kind=='CALL' else 1)
 # The P-code branch skips all instruction side effects if the Zero flag is set.
 p=[op('INT_RIGHT',[v('register',0),v('const',6,4)],v('unique',256)),
    op('INT_AND',[v('unique',256),v('const',1)],v('unique',257)),
    op('INT_EQUAL',[v('unique',257),v('const',0)],v('unique',258)),
    op('BOOL_NEGATE',[v('unique',258)],v('unique',259)),
    op('CBRANCH',[v('ram',fall,2),v('unique',259)])]
 if kind=='CALL':p.extend([
    op('INT_SUB',[v('register',68,2),v('const',2,2)],v('register',68,2)),
    op('STORE',[v('const',401,8),v('register',68,2),v('const',fall,2)],space='ram'),
    op('CALL',[v('ram',0x120)])])
 else:p.extend([
    op('LOAD',[v('const',401,8),v('register',68,2)],v('register',66,2),space='ram'),
    op('INT_ADD',[v('register',68,2),v('const',2,2)],v('register',68,2)),
    op('RETURN',[v('register',66,2)])])
 return {'address':pc,'mnemonic':kind,'fallthrough':fall,'pcode':p}

class ConditionalControlDev(unittest.TestCase):
 def test_guarded_control_instructions_and_rejection(self):
  for kind,pc in [('CALL',0x100),('RET',0x200)]:
   lines=emit_instruction(conditional(pc,kind))
   self.assertTrue(any('if (!(' in line for line in lines),lines)
   self.assertEqual(lines[-1],'}')
  broken=conditional(0x100,'CALL');broken['pcode'][4]['inputs'][0]['offset']=0x234
  with self.assertRaisesRegex(ValueError,'CFG'):emit_instruction(broken)
 def test_compiled_taken_and_not_taken(self):
  self.assertTrue(shutil.which('cmake'),'CMake C++ compiler toolchain is required for mandatory compiled acceptance')
  cases=[]
  for pc,kind in [(0x100,'CALL'),(0x200,'RET')]:
   i=conditional(pc,kind)
   stmt='\n'.join(emit_instruction(i))
   cases.append(f'case 0x{pc:x}: {{ std::uint16_t next=0x{i["fallthrough"]:x}; {stmt} s.pc=next;return true; }}')
  cpp='''#include "runtime.hpp"
#include <cassert>
bool run(rd::State& s){switch(s.pc){'''+ '\n'.join(cases)+'''default:return false;}}
int main(){
 rd::State s;s.rom.resize(0xc000);s.set_register(68,2,0xdffe);s.pc=0x100;
 s.set_register(0,1,0x40);assert(run(s));assert(s.pc==0x103);assert(s.get_register(68,2)==0xdffe);
 s.pc=0x100;s.set_register(0,1,0);assert(run(s));assert(s.pc==0x120);assert(s.get_register(68,2)==0xdffc);assert(s.memory(0xdffc,2)==0x103);
 s.pc=0x200;s.set_register(0,1,0x40);assert(run(s));assert(s.pc==0x201);assert(s.get_register(68,2)==0xdffc);
 s.pc=0x200;s.set_register(0,1,0);assert(run(s));assert(s.pc==0x103);assert(s.get_register(68,2)==0xdffe);
}
'''
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'test.cpp';source.write_text(cpp)
   exe=Path(t)/'test'
   project=Path(t)
   (project/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.17)\nproject(z80_conditional_control LANGUAGES CXX)\nadd_executable(z80_conditional_control test.cpp "'+str(ROOT/'systems/mastersystem/runtime.cpp').replace('\\','/')+'")\ntarget_compile_features(z80_conditional_control PRIVATE cxx_std_17)\ntarget_include_directories(z80_conditional_control PRIVATE "'+str(ROOT/'systems/mastersystem').replace('\\','/')+'" "'+str(ROOT).replace('\\','/')+'")\n')
   for cmd in (['cmake','-S',str(project),'-B',str(project/'build')],['cmake','--build',str(project/'build'),'--config','Release']):
    build=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    self.assertEqual(build.returncode,0,build.stdout+build.stderr)
   names=('z80_conditional_control.exe',) if os.name=='nt' else ('z80_conditional_control',)
   binaries=[item for item in (project/'build').rglob('*') if item.is_file() and item.name in names]
   self.assertTrue(binaries,'Compiled conditional-control executable missing')
   run=subprocess.run([str(binaries[0])],capture_output=True,text=True,timeout=20)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)
if __name__=='__main__':unittest.main()
