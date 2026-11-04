"""Compiled checks for SN76489 register semantics, tone clock and noise output.

Hardware register requirements follow the Sega Master System SN76489 technical
reference (SMS Power). Sample waveform parity with analogue hardware is not claimed.
"""
import tempfile,unittest
from tooling.compiled_fixture_v0445 import run_cpp_fixture
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "hardware/adapters/sms.hpp"
#include <cassert>
#include <cstdint>
using namespace recomp::hw;
int main(){
 sms::Psg p;
 // Tone 0: period 254, standard SMS clock => 440Hz.
 p.write({Space::IO,0x7f},0x8e);
 p.write({Space::IO,0x7f},0x0f);
 p.write({Space::IO,0x7f},0x9f);
 assert(p.sample(0)==0);
 // A data byte after a latched volume register must unmute channel 0.
 p.write({Space::IO,0x7f},0x00);
 assert(p.sample(0)==1500);
 assert(p.sample(254*16)==-1500);
 assert(p.sample(254*32)==1500);
 // A *second* volume data byte must update volume, not be dropped.
 p.write({Space::IO,0x7f},0x0f);
 assert(p.sample(254*32)==0);
 // Noise channel can be enabled on its own; channel 3 is not hard-muted.
 sms::Psg n;
 n.write({Space::IO,0x7f},0xe0); // periodic noise rate 0
 n.write({Space::IO,0x7f},0xf0); // volume 0
 assert(n.sample(0)!=0);
 auto before=n.sample(31*512ull);
 auto after=n.sample(32*512ull);
 assert(before!=after);
 // Data byte after a noise latch can change rate and white-noise mode.
 n.write({Space::IO,0x7f},0xe0);
 n.write({Space::IO,0x7f},0x04); // white, rate 0
 assert(n.sample(40*512ull)!=0);
 return 0;
}
'''
class SmsPsg443(unittest.TestCase):
 def test_compiled_psg_control_and_waveform(self):
  with tempfile.TemporaryDirectory(prefix="recomp-psg-fixture-") as d:
   run_cpp_fixture(SOURCE,ROOT,Path(d))

if __name__=='__main__':unittest.main()
