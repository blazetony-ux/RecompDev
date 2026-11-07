"""Source-verified native pilot stops seed plugin-owned translation recovery.

No game title, external Ghidra install or hardware-specific opcode patch; the
synthetic fixture includes ordinary Z80 CB BIT/RES and conditional RET bytes.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

exe=Path(sys.argv[1]).resolve(strict=True)
plugins=Path(sys.argv[2]).resolve(strict=True)
source_root=Path(sys.argv[3]).resolve(strict=True)

with tempfile.TemporaryDirectory(prefix='rd-native-runtime-gap-') as tmp:
 root=Path(tmp)
 source=bytearray(0x8000)
 source[0x7ff0:0x7ff8]=b'TMR SEGA'
 source[0]=0x76  # HALT at reset, independent of dynamic evidence
 source[0x38]=source[0x66]=0x76
 # Genuine branch target from an arbitrary native stop, not a source hack.
 # LD HL,C078; BIT 7,(HL); RET Z; RES 7,(HL); HALT
 source[0x5346:0x534f]=bytes.fromhex('21 78 c0 cb 7e c8 cb be 76')
 # Generic dynamic recovery: a CALL target is only source-reachable when a
 # genuine observed SP proves the return-address PUSH cannot modify mapper RAM.
 source[0x5320:0x532a]=bytes.fromhex('21 80 c0 11 82 c0 cd 40 53 76')
 source[0x5340:0x5346]=bytes.fromhex('e5 e1 38 01 00 c9')  # PUSH, POP, JR C, NOP, RET
 rom=root/'synthetic.sms';rom.write_bytes(source)
 digest=hashlib.sha256(source).hexdigest()
 base={'schema':'recomp-function-pcode-v1','target_id':'synthetic-runtime-gap-fixture',
       'source_sha256':digest,'analyzer':'synthetic-recovery-test',
       'language':'z80:LE:16:default','bank_context':None,
       'functions':[{'instructions':[]}]}
 export=root/'base.json';export.write_text(json.dumps(base))
 report={'status':'UNTRANSLATED_INITIAL_CODE','native_steps':147,
         'rom_bytes':len(source),'pc':0x5346,'physical_offset':0x5346,
         'mapper':[0,0,1,2]}
 evidence=root/'native-stop.log';evidence.write_text('PILOT_RESULT='+json.dumps(report)+'\n')
 def execute(name,stops,success=True,compile_full=False):
  dest=root/name
  cmd=[str(exe),'--stage','native-translate','--rom',str(rom),
       '--export',str(export),'--allow-synthetic-export',
       '--source-root',str(source_root),'--plugin-dir',str(plugins),
       '--backend','full','--out',str(dest)]
  if not compile_full:cmd.append('--no-compile')
  for stop in stops:cmd.extend(['--runtime-gap-report',str(stop)])
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=70)
  if success:
   assert r.returncode==0,(r.stdout,r.stderr)
   return json.loads((dest/'translation-manifest.json').read_text()),dest
  assert r.returncode!=0,(r.stdout,r.stderr)
  return r.stdout+r.stderr,None
 manifest,dest=execute('translated',[evidence])
 phys={x['physical'] for x in manifest['accepted_instructions']}
 for pc in (0x5346,0x5349,0x534b,0x534c):
  assert pc in phys,(hex(pc),sorted(phys))
 assert manifest['rejected']==0,manifest
 assert manifest['source_decoder_recovered']>=4,manifest
 generated=''.join(x.read_text() for x in [dest/'translated.cpp',*dest.glob('native_part_*.cpp')])
 assert 's.get_register(0u,1u)&64u' in generated, 'conditional RET lowering missing'
 assert 's.write_byte' in generated, 'CB RES memory write missing'
 # Multiple stop reports are supported for additive auto-recovery.
 again=root/'next-stop.json';r2=dict(report,pc=0x5350,physical_offset=0x5350)
 # Keep ROM immutable: use an already present instruction as the second seed.
 r2['pc']=0x534c;r2['physical_offset']=0x534c
 again.write_text(json.dumps(r2))
 manifest2,_=execute('translated-two-stops',[evidence,again])
 assert manifest2['emitted']>=manifest['emitted']
 # A pilot-reported SP permits verified CALL/PUSH/RET analysis through RAM,
 # whereas a pre-SP report must not guess that the mapper survived an unknown
 # stack write. The CPU plugin (not the game or controller) owns this effect.
 call_report=dict(report,pc=0x5320,physical_offset=0x5320,sp=0xdff0)
 call_seed=root/'call-with-stack.json';call_seed.write_text(json.dumps(call_report))
 call_manifest,call_dest=execute('call-stack',[call_seed],compile_full=True)
 assert (call_dest/'build').is_dir(), 'native CALL/JR generated project was not compiled'
 call_phys={x['physical'] for x in call_manifest['accepted_instructions']}
 for pc in (0x5320,0x5323,0x5326,0x5340,0x5341,0x5342,0x5344,0x5345,0x5329):
  assert pc in call_phys,(hex(pc),sorted(call_phys))
 no_stack_report=dict(call_report);del no_stack_report['sp']
 no_stack_seed=root/'call-no-stack.json';no_stack_seed.write_text(json.dumps(no_stack_report))
 no_stack_manifest,_=execute('call-no-stack',[no_stack_seed])
 no_stack_phys={x['physical'] for x in no_stack_manifest['accepted_instructions']}
 assert 0x5340 not in no_stack_phys,'unobserved stack was assumed safe across CALL'
 forged_sp=dict(call_report,sp=65536)
 forged_stack=root/'forged-stack.json';forged_stack.write_text(json.dumps(forged_sp))
 error,_=execute('forged-stack',[forged_stack],False)
 assert 'RUNTIME_STOP_sp_INVALID' in error,error
 corrupt=dict(report,physical_offset=0x5347)
 wrong=root/'forged-physical.json';wrong.write_text(json.dumps(corrupt))
 error,_=execute('forged',[wrong],False)
 assert 'RUNTIME_STOP_PHYSICAL_MAPPING_MISMATCH' in error,error
 corrupt=dict(report,rom_bytes=len(source)+1)
 wrong=root/'forged-size.json';wrong.write_text(json.dumps(corrupt))
 error,_=execute('forged-size',[wrong],False)
 assert 'RUNTIME_STOP_SOURCE_SIZE_OR_EXECUTION_UNVERIFIED' in error,error
 corrupt=dict(report,status='STEP_BUDGET_REACHED')
 wrong=root/'forged-stop.json';wrong.write_text(json.dumps(corrupt))
 error,_=execute('forged-status',[wrong],False)
 assert 'RUNTIME_STOP_REASON_NOT_TRANSLATION_GAP' in error,error
print('PASS observed native stop -> mapper/source-qualified Z80 CB/RET translation; forged evidence rejected')
