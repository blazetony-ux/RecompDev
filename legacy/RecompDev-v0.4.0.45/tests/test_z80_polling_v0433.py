"""A second, independently authored Z80 ROM fixture polls the actual guest V-counter.

This tests translated source logic -> hardware counter -> conditional control flow -> PSG.
There is no game name, ROM-specific patch, or CPU interpreter in the execution path.
"""
import hashlib,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from nativepilot.generator import generate_project
ROOT=Path(__file__).resolve().parents[1]
class ScanlineNativePolling(unittest.TestCase):
 def test_compiled_vcounter_poll_unblocks_translated_control_flow(self):
  self.assertTrue(shutil.which('cmake'),'CMake required')
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp)
   raw=bytearray(0xc000);raw[0:3]=bytes([0xc3,3,0]);
   program=bytes.fromhex('db7e fe80 20fa 3e90 d37f c30d00')
   raw[3:3+len(program)]=program;rom=tmp/'independent-poll.sms';rom.write_bytes(raw)
   def v(sp,size,offset):return {'space':sp,'size':size,'offset':offset}
   ins=[]
   def emit(pc,bs,mnemonic,pcode):
    ins.append({'address':pc,'length':len(bs),'mnemonic':mnemonic,'fallthrough':pc+len(bs),
                'bytes_sha256':hashlib.sha256(bs).hexdigest(),'pcode':pcode})
   emit(3,bytes.fromhex('db7e'),'IN',[{'op':'LOAD','memory_space':'io','inputs':[v('const',1,0),v('const',2,0x7e)],'output':v('register',1,1)}])
   emit(5,bytes.fromhex('fe80'),'CP',[{'op':'INT_NOTEQUAL','inputs':[v('register',1,1),v('const',1,128)],'output':v('unique',1,1)}])
   emit(7,bytes.fromhex('20fa'),'JR',[{'op':'CBRANCH','inputs':[v('ram',1,3),v('unique',1,1)]}])
   emit(9,bytes.fromhex('3e90'),'LD',[{'op':'COPY','inputs':[v('const',1,0x90)],'output':v('register',1,1)}])
   emit(11,bytes.fromhex('d37f'),'OUT',[{'op':'STORE','memory_space':'io','inputs':[v('const',1,0),v('const',2,0x7f),v('register',1,1)]}])
   emit(13,bytes.fromhex('c30d00'),'JP',[{'op':'BRANCH','inputs':[v('ram',1,13)]}])
   doc={'language':'z80:LE:16:default','source_sha256':hashlib.sha256(raw).hexdigest(),
        'target_id':'unknown-sms-application','functions':[{'entry':3,'instructions':ins}]}
   project=tmp/'project';statistics=generate_project(doc,rom,project)
   self.assertGreaterEqual(statistics['translated_instructions'],6)
   for cmd in (['cmake','-S',str(project),'-B',str(project/'build')],['cmake','--build',str(project/'build'),'--config','Release']):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    self.assertEqual(p.returncode,0,p.stdout[-700:]+p.stderr[-2000:])
   candidates=list((project/'build').rglob('RecompDevNativePilot.exe' if os.name=='nt' else 'RecompDevNativePilot'))
   exe=next((x for x in candidates if x.is_file()),None)
   self.assertIsNotNone(exe)
   p=subprocess.run([str(exe),str(rom),'3000'],capture_output=True,text=True,timeout=35)
   self.assertEqual(p.returncode,0,p.stdout[-600:]+p.stderr)
   result=json.loads(next(line.partition('=')[2] for line in p.stdout.splitlines() if line.startswith('PILOT_RESULT=')))
   self.assertEqual(result['status'],'STEP_BUDGET_REACHED',result)
   self.assertGreater(result['vcounter_reads'],500)
   self.assertGreater(result['first_vcounter_read_step'],0)
   self.assertGreaterEqual(result['psg_writes'],1,'The loop should eventually encounter line 128 and exit')
   self.assertGreater(result['timing_qualified_steps'],2000)
   self.assertEqual(result['timing_unqualified_steps'],0)
if __name__=='__main__':unittest.main()
