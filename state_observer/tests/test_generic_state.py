"""Machine-independent recorder tests: no ROM, game or translation dependencies."""
import csv
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from state_observer.analyze import correlate,write_report

ROOT=Path(__file__).resolve().parents[2]

class GenericStateObserverTests(unittest.TestCase):
    def test_compiled_multiple_regions_and_sms_adapter(self):
        compiler=shutil.which('g++') or shutil.which('clang++')
        if not compiler:self.skipTest('C++ compiler missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cpp=root/'observer.cpp'
            cpp.write_text(r'''
#include "rd_state_observer.hpp"
#include "rd_sms_memory_adapter.hpp"
#include <array>
#include <cstdint>
struct MachineState { std::array<std::uint8_t,8192> ram{}; };
int main(){
  std::array<std::uint8_t,3> bank{{10,20,30}};
  std::array<std::uint8_t,2> second{{100,99}};
  const rd_state_observer::MemoryRegionView regions[]={
    {"memory0","other_platform","cpu_alpha",4096,bank.data(),bank.size(),"big","cpu_alpha_cycles"},
    {"memory1","other_platform","cpu_beta",8192,second.data(),second.size(),"little","cpu_beta_cycles"}
  };
  rd_state_observer::sample_memory(0,0,regions,2);
  bank[0]=9;second[0]=101;
  rd_state_observer::sample_memory(100,1,regions,2);
  MachineState sms; sms.ram[0]=20;
  rd_sms_memory_adapter::sample(200,2,sms);
  sms.ram[0]=21; sms.ram[1]=2;
  rd_sms_memory_adapter::sample(300,3,sms);
  return 0;
}
''',encoding='utf8')
            exe=root/'observer'
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',
                '-I',str(ROOT/'state_observer/bridge'),'-I',str(ROOT/'movement_trace/bridge'),
                str(cpp),'-o',str(exe)],check=True,capture_output=True,text=True)
            env=os.environ.copy();env['RECOMPDEV_STATE_TRACE_DIR']=str(root)
            subprocess.run([str(exe)],env=env,check=True,capture_output=True,text=True)
            result=write_report(root,[{'guest_cycle':0,'logical_buttons':0},
                {'guest_cycle':50,'logical_buttons':8},
                {'guest_cycle':250,'logical_buttons':4}],input_clock_domain='z80_tstates')
            self.assertEqual('TRACE_COLLECTED',result['status'])
            self.assertEqual(3,len(result['regions']))
            self.assertEqual(8201,result['observed_deltas']) # 3+2+8192 baseline, 1+1+2+1 deltas
            ids={r['region_id'] for r in result['regions']}
            self.assertEqual({'memory0','memory1','system_wram'},ids)
            self.assertEqual('UNIDENTIFIED_MEMORY_OFFSETS_NOT_PROVEN_PLAYER_COORDINATES',result['candidate_interpretation'])
            self.assertIn('memory0',str(result['candidate_byte_offsets']))

    def test_rejects_inconsistent_delta_chain(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            for name,header,rows in [
             ('state-memory-regions.csv',['region_id','provider','address_space','base_address','size_bytes','byte_order','clock_domain'],
                 [['r','synthetic','cpu0',0,1,'unknown','clock0']]),
             ('state-memory-deltas.csv',['sample_seq','guest_frame','guest_cycle','region_id','offset','previous','current'],
                 [[0,0,0,'r',0,-1,5],[1,1,100,'r',0,7,8]]),
             ('state-memory-summary.csv',['region_id','samples','changes','truncated','truncate_reason'],
                 [['r',2,2,0,'none']])]:
                with (d/name).open('w',encoding='utf8',newline='') as f:
                    w=csv.writer(f);w.writerow(header);w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'preceding observation'):correlate(d)

    def test_no_tracing_when_unset(self):
        compiler=shutil.which('g++') or shutil.which('clang++')
        if not compiler:self.skipTest('C++ compiler missing')
        # Generic header carries no dependency on the SMS provider.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cpp=root/'minimal.cpp'
            cpp.write_text('#include "rd_state_observer.hpp"\n'
                        'int main(){ unsigned char a[1]={3};'
                        'rd_state_observer::MemoryRegionView r={"r","p","cpu",0,a,1,"unknown","cpu"};'
                        'rd_state_observer::sample_memory(0,0,&r,1);return 0;}''',encoding='utf8')
            exe=root/'minimal'
            subprocess.run([compiler,'-std=c++17','-I',str(ROOT/'state_observer/bridge'),str(cpp),'-o',str(exe)],check=True,capture_output=True,text=True)
            env=os.environ.copy();env.pop('RECOMPDEV_STATE_TRACE_DIR',None)
            subprocess.run([str(exe)],env=env,check=True,capture_output=True,text=True)
            self.assertEqual(set(root.iterdir()),{cpp,exe})

if __name__=='__main__':unittest.main()
