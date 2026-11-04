"""Source-attested generated Z80 P-code: prolonged carry loop and bounded diagnostics.

Synthetic bytes only. This tests native C++ progress and carry semantics for one
instruction sequence, not Shinobi parity or accurate Master System timing.
"""
import hashlib
import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from nativepilot.engine import cache_evidence_roots,cache_path_trusted,summarize_trace
from nativepilot.generator import generate_project,sha256

ROOT=Path(__file__).resolve().parents[1]


def var(space,offset,size=1):
    return {'space':space,'offset':offset,'size':size}


def instr(raw,addr,size,mnem,fallthrough,ops):
    return {'address':addr,'length':size,'mnemonic':mnem,
            'fallthrough':fallthrough,'bytes_sha256':hashlib.sha256(raw[addr:addr+size]).hexdigest(),
            'pcode':ops}

def independent_z80_subset(raw, steps):
    """Independent byte-level oracle for JP, LD, ADD HL,DE, JR C, DJNZ, HALT.

    Not a game emulator. Intentionally does not consume the generated P-code.
    """
    pc=0;de=0;hl=0;b=0;carry=0
    seen={0:(pc,b,hl,de,carry)}
    points={1000,10000,50000,100000,250000,500000,1000000,2000000}
    for step in range(1,steps+1):
        op=raw[pc]
        if op==0xc3:
            pc=raw[pc+1]|raw[pc+2]<<8
        elif op==0x11:
            de=raw[pc+1]|raw[pc+2]<<8;pc+=3
        elif op==0x06:
            b=raw[pc+1];pc+=2
        elif op==0x21:
            hl=raw[pc+1]|raw[pc+2]<<8;pc+=3
        elif op==0x19:
            val=hl+de;carry=int(val>0xffff);hl=val&0xffff;pc+=1
        elif op==0x38:
            rel=raw[pc+1] if raw[pc+1]<128 else raw[pc+1]-256
            pc=pc+2+(rel if carry else 0)
        elif op==0x10:
            b=(b-1)&255
            rel=raw[pc+1] if raw[pc+1]<128 else raw[pc+1]-256
            pc=pc+2+(rel if b else 0)
        elif op==0x76:pc+=1
        else:raise AssertionError(f'Unexpected oracle opcode {op:#x} at {pc:#x}')
        if step in points or step==steps:seen[step]=(pc,b,hl,de,carry)
        if op==0x76:break
    return seen

class StartupLoopTests(unittest.TestCase):
    def test_imported_bank_cache_root_is_fixed_and_legacy_is_readable(self):
        with tempfile.TemporaryDirectory() as dirname:
            parent=Path(dirname);cur=parent/'RecompDev-v0.4.0.14'
            old=parent/'RecompDev-v0.4.0.5'/'evidence'/'native-pilot-v0405'/'jobs'/'job-1'/'bank-functions.json'
            new=cur/'evidence'/'native-pilot-v0414'/'jobs'/'job-2'/'bank-functions.json'
            prior=parent/'RecompDev-v0.4.0.8'/'evidence'/'native-pilot-v0408'/'jobs'/'job-1'/'bank-functions.json'
            arbitrary=parent/'not-trusted'/'bank-functions.json'
            self.assertTrue(cache_path_trusted(old,cur))
            self.assertTrue(cache_path_trusted(new,cur))
            self.assertTrue(cache_path_trusted(prior,cur))
            self.assertFalse(cache_path_trusted(arbitrary,cur))
            self.assertFalse(cache_path_trusted(parent/'RecompDev-v0.4.0.4'/'evidence'/'native-pilot-v0404'/'jobs'/'x',cur))
            self.assertTrue(cache_path_trusted(parent/'RecompDev-v0.4.0.10'/'evidence'/'native-pilot-v0410'/'jobs'/'legacy'/'bank-functions.json',cur))
            self.assertEqual(len(cache_evidence_roots(cur)),16)

    def test_loop_observation_cannot_claim_parity(self):
        x=summarize_trace({'native_steps':50000,'hotspots':[{'count':24950},{'count':24949}],
                           'checkpoints':[{'step':0},{'step':50000}]})
        self.assertTrue(x['repetitive_execution_observed'])
        self.assertTrue(x['loop_not_proven_infinite'])
        self.assertEqual(x['reference_parity'],'NOT_TESTED')

    @unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),
                         'CMake and native C++ compiler required')
    def test_attested_previous_bank_export_is_reused_without_ghidra(self):
        import sqlite3
        from unittest.mock import patch
        from test_autonomous_bank_recovery_v0405 import BankRecoveryTests
        from nativepilot.engine import pilot,SCHEMA
        BankRecoveryTests.setUp(self)
        bank=BankRecoveryTests.fake_bank_doc(self)
        previous=self.root/'previous-evidence'/'bank-functions.json'
        previous.parent.mkdir();previous.write_text(json.dumps(bank))
        con=sqlite3.connect(str(self.db));con.executescript(SCHEMA)
        con.execute('INSERT INTO native_bank_evidence_v0405 VALUES(?,?,?,?,?,?)',
                    (self.sha,2,3,0x8000,str(previous),'2026-10-31T18:00:00+00:00'))
        con.commit();con.close()
        with patch('nativepilot.engine.cache_path_trusted',side_effect=lambda path,root: Path(path)==previous):
            result=pilot(self.db,self.sha,self.root/'cache-run',[self.roms],max_steps=20,max_recoveries=0)
        self.assertEqual(result['reused_bank_exports'],1,result)
        self.assertEqual(result['trace']['native_steps'],8,result)
        self.assertEqual(result['trace']['physical_offset'],0xc005)
        self.assertEqual(result['trace']['vdp_control_writes'],0)

    @unittest.skipUnless(shutil.which('cmake') and shutil.which('g++'),
                         'CMake and native C++ compiler required')
    def test_native_shinobi_shaped_carry_loop_exits_above_250k(self):
        with tempfile.TemporaryDirectory() as dirname:
            root=Path(dirname);raw=bytearray(64*1024)
            # Actual Z80 machine bytes for a synthetic DE=FFFF / HL=39DE / B=10 loop.
            # Same ADD HL,DE / JR C / DJNZ structure as the user's startup trace.
            raw[:3]=b'\xc3\xa0\x00'
            table={0xa0:b'\x11\xff\xff',0xa3:b'\x06\x0a',
                   0xa5:b'\xc3\xa9\x00',0xa9:b'\x21\xde\x39',
                   0xac:b'\x19',0xad:b'\x38\xfd',
                   0xaf:b'\x10\xf8',0xb1:b'\x76'}
            for pc,code in table.items():raw[pc:pc+len(code)]=code
            rom=root/'SyntheticCarryLoop.sms';rom.write_bytes(raw)
            f=[
              instr(raw,0xa0,3,'LD',0xa3,[{'op':'COPY','output':var('register',4,2),'inputs':[var('const',0xffff,2)]}]),
              instr(raw,0xa3,2,'LD',0xa5,[{'op':'COPY','output':var('register',3),'inputs':[var('const',10)]}]),
              instr(raw,0xa5,3,'JP',None,[{'op':'BRANCH','inputs':[var('ram',0xa9)]}]),
              instr(raw,0xa9,3,'LD',0xac,[{'op':'COPY','output':var('register',6,2),'inputs':[var('const',14814,2)]}]),
              instr(raw,0xac,1,'ADD',0xad,[
                {'op':'INT_CARRY','output':var('unique',100),'inputs':[var('register',6,2),var('register',4,2)]},
                {'op':'COPY','output':var('register',0),'inputs':[var('unique',100)]},
                {'op':'INT_ADD','output':var('register',6,2),'inputs':[var('register',6,2),var('register',4,2)]}]),
              instr(raw,0xad,2,'JR',0xaf,[{'op':'CBRANCH','inputs':[var('ram',0xac),var('register',0)]}]),
              instr(raw,0xaf,2,'DJNZ',0xb1,[
                {'op':'INT_SUB','output':var('register',3),'inputs':[var('register',3),var('const',1)]},
                {'op':'INT_NOTEQUAL','output':var('unique',101),'inputs':[var('register',3),var('const',0)]},
                {'op':'CBRANCH','inputs':[var('ram',0xa9),var('unique',101)]}]),
              instr(raw,0xb1,1,'HALT',None,[{'op':'CALLOTHER','inputs':[var('const',9,4)]}]),
            ]
            doc={'schema':'recomp-function-pcode-v1','source_sha256':sha256(rom),
                 'target_id':'mastersystem-synthetic-carry','language':'z80:LE:16:default',
                 'functions':[{'entry':0xa0,'name':'SYNTHETIC_DELAY','instructions':f}]}
            project=root/'native-project';generation=generate_project(doc,rom,project)
            self.assertEqual(generation['translated_instructions'],9) # reset jump + 8 loop instructions
            subprocess.run(['cmake','-S',str(project),'-B',str(project/'build')],check=True,capture_output=True)
            subprocess.run(['cmake','--build',str(project/'build'),'--config','Release','--parallel','2'],check=True,capture_output=True)
            # CMake's Visual Studio generator also emits RecompDevNativePilot.vcxproj;
            # permission bits/glob prefixes cannot identify executables on Windows.
            build=project/'build'
            if os.name=='nt':
                candidates=(build/'Release'/'RecompDevNativePilot.exe',
                            build/'RecompDevNativePilot.exe')
            else:
                candidates=(build/'RecompDevNativePilot',)
            exe=[path for path in candidates if path.is_file()]
            self.assertTrue(exe, 'Expected actual compiled RecompDevNativePilot product')
            proc=subprocess.run([str(exe[0]),str(rom),'500000'],capture_output=True,text=True,check=True,timeout=30)
            trace=json.loads(next(line.split('=',1)[1] for line in proc.stdout.splitlines() if line.startswith('PILOT_RESULT=')))
            self.assertEqual(trace['status'],'HALT_AWAITING_INTERRUPT',trace)
            self.assertEqual(trace['pc'],0xb2)
            self.assertGreater(trace['native_steps'],250000)
            self.assertLess(trace['native_steps'],400000)
            self.assertEqual(trace['bc']>>8,0)
            expected=independent_z80_subset(raw,trace['native_steps'])
            for checkpoint in trace['checkpoints']:
                pc,b,hl,de,carry=expected[checkpoint['step']]
                self.assertEqual(checkpoint['pc'],pc,checkpoint)
                self.assertEqual(checkpoint['bc']>>8,b,checkpoint)
                self.assertEqual(checkpoint['hl'],hl,checkpoint)
                self.assertEqual(checkpoint['de'],de,checkpoint)
                self.assertEqual(checkpoint['af']&1,carry,checkpoint)
            self.assertGreater(trace['hotspots'][0]['count'],100000)
            self.assertTrue(any(c['step']==250000 for c in trace['checkpoints']))
            self.assertEqual(trace['vdp_data_writes'],0)
            self.assertEqual(trace['first_vdp_port_step'],0)
            self.assertEqual(trace['psg_writes'],0)
            self.assertEqual(summarize_trace(trace)['reference_parity'],'NOT_TESTED')

if __name__=='__main__':unittest.main()
