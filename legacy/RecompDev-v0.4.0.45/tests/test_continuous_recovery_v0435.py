"""No proprietary ROM. Two real source-attested native C++ builds and reset replay."""
import hashlib,json,os,shutil,tempfile,unittest
from pathlib import Path
from nativecore.continuous_recovery_v0435 import run
from nativepilot.generator import verify_export


def fixture(root):
    root=Path(root)
    rom=root/'fixture.sms'
    raw=bytearray(32768)
    raw[:9]=b'\xc3\x03\x00\xc3\x06\x00\xc3\x06\x00'
    raw[0x7ff0:0x7ff8]=b'TMR SEGA'
    rom.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    def entry(pc):
        return {'address':pc,'length':3,'fallthrough':pc+3,'mnemonic':'JP',
                'bytes_sha256':hashlib.sha256(raw[pc:pc+3]).hexdigest(),
                'pcode':[{'op':'BRANCH','inputs':[{'space':'ram','offset':6 if pc==3 else pc,'size':1}]}]}
    initial={'schema':'recomp-function-pcode-v1','source_sha256':digest,'target_id':'synthetic',
             'language':'z80:LE:16:default','functions':[{'entry':3,'name':'main','instructions':[entry(3)]}]}
    overlay={'schema':'recomp-function-pcode-v1','source_sha256':digest,'target_id':'synthetic',
             'language':'z80:LE:16:default','bank_context':{'slot':0,'bank':0,'base':0,'physical_start':0},
             'functions':[{'entry':6,'name':'recovered','instructions':[entry(6)]}]}
    exp=root/'initial.json';exp.write_text(json.dumps(initial))
    return rom,exp,overlay

class ContinuousRecovery435(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rom,self.export,self.overlay=fixture(self.root)
    def recover(self,rom,sha,target,pc,mapper,out):
        self.assertEqual(pc,6);self.assertEqual(mapper[1],0)
        recovered,_,_=verify_export(self.overlay,rom)
        self.assertIn(6,recovered)
        (out/'bank-functions.json').write_text(json.dumps(self.overlay))
        return self.overlay,{'status':'SOURCE_BYTES_VERIFIED','pc':pc,'physical_offset':6}
    def test_recovery_rebuilds_and_replays_compiled_cpp(self):
        if not shutil.which('cmake') or not (os.name=='nt' or shutil.which('g++') or shutil.which('clang++')):
            self.fail('Compiled recovery acceptance requires CMake and a C++ toolchain')
        result=run(self.rom,self.export,self.root/'job',frames=2,steps=1000,max_recoveries=2,recover=self.recover)
        self.assertEqual(result['status'],'STOPPED_WITHOUT_RECOVERABLE_CODE',result)
        self.assertEqual([x['status'] for x in result['attempts']],
            ['UNTRANSLATED_INITIAL_CODE','STEP_BUDGET_REACHED'])
        self.assertEqual(result['recovered_entries'],1)
        self.assertEqual(result['attempt_count'],2)
        self.assertTrue(result['attempts'][1]['previous_stop_reached_or_surpassed'])
        self.assertNotEqual(result['attempts'][0]['executable_sha256'],result['attempts'][1]['executable_sha256'])
        self.assertTrue((self.root/'job'/'continuous-recovery-report.json').exists())
        self.assertFalse(result['attempts'][1].get('native_qualified',False))
    def test_wrong_source_is_rejected_before_output(self):
        modified=bytearray(self.rom.read_bytes());modified[3]=0
        self.rom.write_bytes(modified)
        with self.assertRaisesRegex(ValueError,'ROM differs'):
            run(self.rom,self.export,self.root/'reject',max_recoveries=1)
        self.assertFalse((self.root/'reject').exists())
    def test_no_recursion_on_non_new_entry(self):
        def fake_build(project):
            binary=project/'build'/'RecompDevNativePilot';binary.parent.mkdir(exist_ok=True)
            binary.write_text('stand-in-for-traced-compile');return binary,''
        def fake_session(project,rom,source,out,frames,steps,input_file):
            return {'source_sha256':source,'status':'UNTRANSLATED_INITIAL_CODE','pc':6,'mapper':[0,0,1,2],
                    'physical_offset':6,'native_steps':2,'frames':0,'reference_parity':'NOT_TESTED',
                    'gameplay':'NOT_ESTABLISHED'}
        old=self.overlay.copy();old['functions']=[{'entry':3,'name':'old','instructions':json.loads(self.export.read_text())['functions'][0]['instructions']}]
        result=run(self.rom,self.export,self.root/'blocked',max_recoveries=2,
                   recover=lambda *args:(old,{}),build=fake_build,session=fake_session)
        self.assertEqual(result['status'],'RECOVERY_BLOCKED')
        self.assertIn('not source-attested',result['blocker'])
if __name__=='__main__':unittest.main()
