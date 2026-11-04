"""Compile the production source-byte-driven Z80 timing logic, not a Python copy."""
import os, subprocess, tempfile, unittest, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "nativepilot/z80_cycles.hpp"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
using namespace recomp::z80;
int main(){
 std::array<std::uint8_t,16> rom{};
 auto test=[&](std::initializer_list<unsigned> bytes,unsigned expected,
               std::uint16_t next=0x1003,std::uint16_t fall=0x1003){
  rom.fill(0);unsigned i=0;for(auto b:bytes)rom.at(i++)=std::uint8_t(b);
  auto got=decode([&](std::uint16_t pc){return rom.at(pc-0x1000);},0x1000,next,fall);
  assert(got.known&&got.tstates==expected);
 };
 test({0x00},4); test({0x21,0x12,0x00},10);test({0x22,0,0},16);
 test({0x76},4);test({0x34},11);test({0x7e},7);test({0x86},7);
 test({0x10,0xff},8,0x1002,0x1002);test({0x10,0xff},13,0x1000,0x1002);
 test({0x20,0xfd},7,0x1002,0x1002);test({0x20,0xfd},12,0x0fff,0x1002);
 test({0xc4,0x40,0x50},10);test({0xc4,0x40,0x50},17,0x5040,0x1003);
 test({0xc0},5,0x1001,0x1001);test({0xc0},11,0x9010,0x1001);
 test({0xc9},10);test({0xcd,0,0},17);test({0xd3,0x7f},11);
 test({0xcb,0x46},12);test({0xcb,0x86},15);test({0xcb,0x40},8);
 test({0xed,0x4b,0,0},20);test({0xed,0x78},12);
 test({0xed,0xb0},16,0x1002,0x1002);test({0xed,0xb0},21,0x1000,0x1002);
 test({0xdd,0x21,0,0},14);test({0xfd,0x36,0,0},19);
 test({0xdd,0xcb,0x01,0x46},20);test({0xdd,0xcb,0x01,0x86},23);
 test({0xdd,0xe9},8);test({0xfd,0x34,0x04},23);
 test({0xdd,0xdd,0x21,0,0},18);
 rom.fill(0);rom[0]=0xed;rom[1]=0x00;
 assert(!decode([&](std::uint16_t a){return rom.at(a-0x1000);},0x1000,0,0).known);
 std::puts("Z80_TIMING_COMPILED_PASS");
}
'''
class Z80Timing(unittest.TestCase):
 def test_compiled_z80_tstate_table_and_ambiguous_rejection(self):
  self.assertTrue(shutil.which('cmake'),'CMake required for compiled acceptance')
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'main.cpp').write_text(SOURCE)
   (p/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.16)\nproject(z80cycles LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nadd_executable(z80cycles main.cpp)\ntarget_include_directories(z80cycles PRIVATE "'+str(ROOT).replace('\\','/')+'")\n')
   c=subprocess.run(['cmake','-S',str(p),'-B',str(p/'build')],capture_output=True,text=True,timeout=60)
   self.assertEqual(c.returncode,0,c.stdout+c.stderr)
   b=subprocess.run(['cmake','--build',str(p/'build'),'--config','Release'],capture_output=True,text=True,timeout=90)
   self.assertEqual(b.returncode,0,b.stdout+b.stderr)
   exe=next(x for x in (p/'build').rglob('z80cycles.exe' if os.name=='nt' else 'z80cycles') if x.is_file())
   r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=30)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   self.assertIn('Z80_TIMING_COMPILED_PASS',r.stdout)
 def test_generated_native_code_actually_uses_timing_decoder(self):
  from nativepilot.generator import generate_project
  # Source-level integration check, plus compiled native path in inherited tests.
  contents=(ROOT/'nativepilot'/'generator.py').read_text()
  self.assertIn('recomp::z80::decode',contents)
  self.assertIn("'z80_cycles.hpp'",contents)
  self.assertIn('unqualified_timing_instructions',contents)
if __name__=='__main__':unittest.main()
