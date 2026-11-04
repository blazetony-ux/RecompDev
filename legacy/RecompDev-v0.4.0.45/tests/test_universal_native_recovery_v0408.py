"""No game ROM dependency. Two different synthetic SMS images exercise same native recovery.

The adapter registry also explicitly rejects cross-ISA native-execution claims.
"""
import hashlib,json,os,shutil,sqlite3,tempfile,unittest
from pathlib import Path
from nativecore.registry import capabilities,all_capabilities
from nativecore.recovery import classify,RecoveryPlanner
from nativepilot.engine import pilot
from nativepilot.generator import sha256
from nativepilot.recovery import recover_bank
from discovery.store import connect,store_source
from nativeprep.engine import prepare

ROOT=Path(__file__).resolve().parents[1]
def v(sp,offset,size=1):return {'space':sp,'offset':offset,'size':size}
def copy(dst,src):return {'op':'COPY','output':dst,'inputs':[src]}
def ins(blob,pc,code,mnemonic,fall,ops):
 blob[pc:pc+len(code)]=code
 return {'address':pc,'length':len(code),'bytes_sha256':hashlib.sha256(code).hexdigest(),
         'mnemonic':mnemonic,'fallthrough':fall,'pcode':ops}

class UniversalCapabilityTests(unittest.TestCase):
 def test_registry_disclaims_unimplemented_cross_system_execution(self):
  matrix=all_capabilities()
  self.assertEqual(len(matrix['architectures']),3)
  self.assertEqual(capabilities('megadrive')['cpu'],'m68k')
  self.assertFalse(capabilities('megadrive')['native_execution'])
  self.assertEqual(capabilities('psx-exe')['cpu'],'mips')
  self.assertFalse(capabilities('psx-exe')['native_execution'])
  self.assertTrue(capabilities('mastersystem')['native_execution'])
  self.assertFalse(capabilities('gamegear')['native_execution'])
  self.assertIn('SYSTEM_ADAPTER_MISSING',capabilities('madeup')['blockers'])

 def test_recovery_planner_resolves_bank_fixed_vector_and_budget(self):
  initial={'pc':0x38,'mapper':[0,0,1,6],'status':'UNTRANSLATED_INITIAL_CODE'}
  vector=classify('mastersystem',262144,initial)
  self.assertEqual((vector.region,vector.physical_offset,vector.bank),('fixed-rom-vector',0x38,0))
  bank=classify('mastersystem',262144,{'pc':0x8a68,'mapper':[0,0,1,6],'status':'BANKED_CODE_NOT_TRANSLATED'})
  self.assertEqual((bank.region,bank.physical_offset,bank.bank),('mapped-rom-bank',0x18a68,6))
  plan=RecoveryPlanner(2)
  self.assertEqual(plan.claim(vector),'RECOVERY_QUEUED')
  self.assertEqual(plan.claim(vector),'REPEATED_STOP_NO_NEW_EVIDENCE')
  self.assertEqual(plan.claim(bank),'RECOVERY_QUEUED')
  self.assertEqual(plan.claim(classify('mastersystem',262144,{'pc':0x66,'mapper':[0,0,1,6], 'status':'UNTRANSLATED_INITIAL_CODE'})), 'RECOVERY_BUDGET_EXHAUSTED')
  self.assertIsNone(classify('mastersystem',262144,{'pc':0x38,'mapper':[0,0,1,6],'status':'STEP_BUDGET_REACHED'}))
  with self.assertRaisesRegex(ValueError,'NOT_INTEGRATED'):
   classify('megadrive',65536,initial)

@unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),'CMake/C++ compiler required')
class IndependentZ80Cartridges(unittest.TestCase):
 def run_case(self,label,watched_addr,handler_value):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);romroot=root/'rom';romroot.mkdir()
   raw=bytearray(65536)
   ah=watched_addr&0xff
   bx={}
   def add(pc,code,mnemonic,fall,ops,handler=False):
    (bx.setdefault('handler' if handler else 'startup',[])).append(ins(raw,pc,code,mnemonic,fall,ops))
   add(0,b'\xc3\x00\x01','JP',None,[{'op':'BRANCH','inputs':[v('ram',0x100)]}])
   add(0x38,bytes([0x3e,handler_value]),'LD',0x3a,[copy(v('register',1),v('const',handler_value))],True)
   add(0x3a,bytes([0x32,ah,0xc0]),'LD',0x3d,[copy(v('ram',watched_addr),v('register',1))],True)
   add(0x3d,b'\xc9','RET',None,[{'op':'LOAD','memory_space':'ram','output':v('register',66,2),'inputs':[v('const',401,8),v('register',68,2)]}, {'op':'INT_ADD','output':v('register',68,2),'inputs':[v('register',68,2),v('const',2,2)]},{'op':'RETURN','inputs':[v('register',66,2)]}],True)
   add(0x100,b'\x31\xfe\xdf','LD',0x103,[copy(v('register',68,2),v('const',0xdffe,2))])
   add(0x103,b'\x3e\x20','LD',0x105,[copy(v('register',1),v('const',0x20))])
   for pc in (0x105,0x109):
    add(pc,b'\xd3\xbf','OUT',pc+2,[{'op':'STORE','memory_space':'io','inputs':[v('const',529,8),v('const',0xbf,2),v('register',1)]}])
   add(0x107,b'\x3e\x81','LD',0x109,[copy(v('register',1),v('const',0x81))])
   add(0x10b,b'\xfb','EI',0x10c,[{'op':'CALLOTHER','inputs':[v('const',5,4)]}])
   add(0x10c,bytes([0x3a,ah,0xc0]),'LD',0x10f,[copy(v('register',1),v('ram',watched_addr))])
   add(0x10f,b'\xb7','OR',0x110,[{'op':'INT_EQUAL','output':v('unique',100),'inputs':[v('register',1),v('const',0)]}])
   add(0x110,b'\x28\xfa','JR',0x112,[{'op':'CBRANCH','inputs':[v('ram',0x10c),v('unique',100)]}])
   add(0x112,b'\x76','HALT',None,[{'op':'CALLOTHER','inputs':[v('const',9,4)]}])
   raw[0x7ff0:0x7ff8]=b'TMR SEGA'
   rom=romroot/(label+'.sms');rom.write_bytes(raw)
   digest=sha256(rom);db=root/'catalogue.sqlite';shutil.copyfile(ROOT/'catalogue.sqlite',db)
   con=connect(db);store_source(con,digest,rom,len(raw),'SHA256_COMPLETE','mastersystem',label,'Independent synthetic program');con.close()
   prep=prepare(db,digest,root/'prep',allowed_roots=[romroot],analyze=False)
   target=prep['target_id']
   base={'schema':'recomp-function-pcode-v1','language':'z80:LE:16:default','source_sha256':digest,'target_id':target}
   (root/'startup.json').write_text(json.dumps({**base,'functions':[{'entry':0,'instructions':bx['startup']}]}))
   con=sqlite3.connect(db);con.execute('UPDATE native_preparations_v0403 SET export_path=? WHERE source_id=?',(str(root/'startup.json'),digest));con.commit();con.close()
   calls=[]
   def fake_analyzer(source,src_sha,tgt,pc,mapper,output):
    calls.append((pc,mapper[:]))
    self.assertEqual((src_sha,tgt),(digest,target))
    self.assertEqual(pc,0x38)
    output.mkdir(parents=True,exist_ok=True)
    doc={**base,'functions':[{'entry':0x38,'instructions':bx['handler']}],
         'bank_context':{'slot':0,'bank':0,'base':0,'physical_start':0}}
    (output/'bank-functions.json').write_text(json.dumps(doc))
    return doc,{'status':'SOURCE_BYTES_VERIFIED','slot':0,'bank':0,'pc':pc,'instructions':len(bx['handler'])}
   report=pilot(db,digest,root/'out',[romroot],max_steps=18000,max_recoveries=1,
                recovery_function=fake_analyzer,watch_addresses=[watched_addr])
   self.assertEqual(len(calls),1,report)
   self.assertEqual(report['recovery_attempts'][0]['pc'],0x38,report)
   self.assertEqual(report['recovery_attempts'][0]['recovery_target']['region'],'fixed-rom-vector',report)
   self.assertEqual(report['recovery_attempts'][0]['recovery'],'CODE_SOURCE_VERIFIED',report)
   self.assertGreater(report['native_steps'],report['recovery_attempts'][0]['native_steps'])
   self.assertGreater(report['trace']['maskable_interrupts'],0)
   w=report['trace']['watched_memory'][0]
   self.assertEqual(w['address'],watched_addr)
   self.assertEqual(w['value'],handler_value)
   self.assertEqual(w['nonzero_writes'],1)
   self.assertEqual(sha256(rom),digest)
   return report

 def test_first_synthetic_cartridge_recovers_fixed_vector(self):
  r=self.run_case('IndependentA',0xc001,1)
  self.assertEqual(r['trace']['last_c001_value'],1)

 def test_second_synthetic_cartridge_without_game_specific_rules(self):
  r=self.run_case('IndependentB',0xc002,2)
  self.assertEqual(r['trace']['watched_memory'][0]['value'],2)

class BrowserCapabilityContract(unittest.TestCase):
 def test_workbench_exposes_capability_endpoint_and_generic_watches(self):
  source=(ROOT/'workbench.py').read_text()
  html=(ROOT/'static/execution.html').read_text()
  js=(ROOT/'static/execution.js').read_text()
  self.assertIn('/api/native-capabilities',source)
  self.assertIn('adapter-capabilities',html)
  self.assertIn('pilot-watches',html)
  self.assertIn('watch_addresses',js)

@unittest.skipUnless(os.name!='nt','Synthetic Ghidra launcher uses a POSIX shebang')
class FixedVectorGhidraHandoff(unittest.TestCase):
 def test_fixed_vector_seeded_without_shinobi_or_bank6_constants(self):
  with tempfile.TemporaryDirectory() as dirname:
   root=Path(dirname);rom=root/'AnotherCartridge.sms'
   image=bytearray(65536);image[0x38:0x3a]=b'\x3e\x01';image[0x7ff0:0x7ff8]=b'TMR SEGA';rom.write_bytes(image)
   digest=sha256(rom)
   stub=root/'fake-ghidra';stub.write_text('''#!/usr/bin/env python3
import hashlib,json,sys,pathlib
argv=sys.argv[1:];base=int(argv[argv.index('-loader-baseAddr')+1],0)
seed=int(argv[argv.index('-preScript')+2],0)
assert base==0 and seed==0x38
source=pathlib.Path(argv[argv.index('-import')+1]).read_bytes()
assert source[0x38:0x3a]==b'\\x3e\\x01'
p=argv.index('-postScript');out,target,digest=argv[p+2:p+5]
ins={'address':seed,'length':2,'fallthrough':seed+2,'mnemonic':'LD',
'bytes_sha256':hashlib.sha256(source[seed:seed+2]).hexdigest(),
'pcode':[{'op':'COPY','output':{'space':'register','offset':1,'size':1},
'inputs':[{'space':'const','offset':1,'size':1}]}]}
pathlib.Path(out).write_text(json.dumps({'source_sha256':digest,'target_id':target,'language':'z80:LE:16:default','functions':[{'entry':seed,'instructions':[ins]}]}))
''');stub.chmod(0o755)
   doc,meta=recover_bank(rom,digest,'mastersystem-test',0x38,[0,0,1,2],root/'recovered',str(stub))
   self.assertEqual(meta['physical_offset'],0x38)
   self.assertEqual((doc['bank_context']['slot'],doc['bank_context']['bank']),(0,0))
   self.assertEqual(doc['functions'][0]['entry'],0x38)

class MultiIsaPreparationTests(unittest.TestCase):
 def test_md_and_psx_registration_share_catalogue_but_not_executable_claim(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);images=root/'images';images.mkdir()
   db=root/'catalogue.sqlite';shutil.copyfile(ROOT/'catalogue.sqlite',db)
   for filename,system,buf,cpu in [
     ('OtherSystem.md','megadrive',bytearray(0x4000),'m68k'),
     ('OtherSystem.exe','psx-exe',bytearray(0x1000),'mips')]:
    if system=='megadrive':buf[0x100:0x104]=b'SEGA'
    else:buf[0:8]=b'PS-X EXE'
    source=images/filename;source.write_bytes(buf);digest=sha256(source)
    con=connect(db);store_source(con,digest,source,len(buf),'SHA256_COMPLETE',system,system,'synthetic header');con.close()
    result=prepare(db,digest,root/('prep-'+cpu),allowed_roots=[images],analyze=False)
    self.assertEqual(result['cpu'],cpu,result)
    self.assertIsNotNone(result['target_id'],result)
    self.assertFalse(capabilities(system)['native_execution'])
    blocked=pilot(db,digest,root/('attempt-'+cpu),[images],compile_native=False)
    self.assertEqual(blocked['status'],'PILOT_BLOCKED',blocked)
    self.assertIn('not integrated',blocked['blocker'])
