"""v0.4.2 deterministic orchestration tests. Synthetic reports are NOT game qualification."""
import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from modular.recovery_manager import run_bounded,hardware_diagnostics


def simulated(rounds):
    index = {'n':0}
    def invoke(pid,args,run_dir,timeout):
        assert pid == 'legacy.recovery'
        assert '--coverage-cache' in args
        n=index['n'];index['n']+=1
        doc=rounds[n]
        out=Path(args[args.index('--output-dir')+1]);out.mkdir()
        (out/'continuous-recovery-report.json').write_text(json.dumps(doc))
        return {'return_code':2 if doc['status']!='CONTINUOUS_SESSION_COMPLETE' else 0,
                'status':'BLOCKED_OR_FAILED' if doc['status']!='CONTINUOUS_SESSION_COMPLETE' else 'COMPLETE'}
    return invoke,index


def d(status, blocker='', entries=0, steps=0, frames=0, pc=30, offset=30):
    return {'status':status,'blocker':blocker,'recovered_entries':entries,
            'maximum_steps_observed':steps,'maximum_frames_observed':frames,
            'coverage_cache':{'mode':'SOURCE_REATTESTED_SQLITE'},
            'attempts':[{'status':'UNTRANSLATED_INITIAL_CODE','pc':pc,'physical_offset':offset,
                         'native_steps':steps,'frames':frames,'vdp_writes':91,'psg_writes':7,
                         'cram_nonzero_bytes':0,'audio_nonzero_samples':0,
                         'frame_hashes_count':frames,'maskable_interrupts':1}]}

class TestRecoveryManager(unittest.TestCase):
    def run_manager(self,docs,**kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            invoke,counter=simulated(docs)
            result,services=run_bounded(invoke,['--coverage-cache',root/'cache.sqlite'],
                   root/'recovery',root/'logs',capture=True,timeout=120,**kwargs)
            self.assertTrue((root/'recovery/continuous-recovery-report.json').is_file())
            self.assertEqual(result,json.loads((root/'recovery/continuous-recovery-report.json').read_text()))
            self.assertEqual(counter['n'],len(services))
            return result
    def test_recovery_continues_until_frame_limit(self):
        x=self.run_manager([d('RECOVERY_BLOCKED','RECOVERY_BUDGET_EXHAUSTED',70,7,0,35432,100968),
                            d('RECOVERY_BLOCKED','RECOVERY_BUDGET_EXHAUSTED',1466,338468,64,56,56),
                            d('CONTINUOUS_SESSION_COMPLETE','',0,500000,120,12,12)],max_rounds=3)
        self.assertEqual(x['status'],'CONTINUOUS_SESSION_COMPLETE')
        self.assertEqual(x['maximum_steps_observed'],500000)
        self.assertEqual(x['recovered_entries'],1536)
        self.assertEqual(x['rounds_completed'],3)
    def test_no_new_code_stops_without_repeated_run(self):
        x=self.run_manager([d('RECOVERY_BLOCKED','RECOVERY_BUDGET_EXHAUSTED',0,338,12)],max_rounds=9)
        self.assertEqual(x['stop_reason'],'RECOVERY_NO_NEW_ATTESTED_CODE')
        self.assertEqual(x['rounds_completed'],1)
    def test_max_rounds_is_hard_bound(self):
        x=self.run_manager([d('RECOVERY_BLOCKED','RECOVERY_BUDGET_EXHAUSTED',70,7,0),
                            d('RECOVERY_BLOCKED','RECOVERY_BUDGET_EXHAUSTED',44,15,1)],max_rounds=2)
        self.assertEqual(x['stop_reason'],'CONTINUATION_ROUND_LIMIT_REACHED')
        self.assertEqual(x['rounds_completed'],2)
    def test_step_budget_not_called_recovery_failure(self):
        x=self.run_manager([d('STOPPED_WITHOUT_RECOVERABLE_CODE','STEP_BUDGET_REACHED',0,200000,38)],max_rounds=3)
        self.assertEqual(x['stop_reason'],'EXECUTION_STEP_BUDGET_REACHED')
        self.assertEqual(x['maximum_steps_observed'],200000)
    def test_hardware_not_equated_to_gameplay_parity(self):
        h=hardware_diagnostics([d('RECOVERY_BLOCKED',frames=64)['attempts'][0]],True)
        self.assertEqual(h['audio_activity'],'GUEST_PSG_WRITES_BUT_SILENT_CAPTURE')
        self.assertEqual(h['interrupt_observation'],'LOW_MASKABLE_INTERRUPT_COUNT_REVIEW')
        self.assertEqual(h['gameplay_parity'],'NOT_ESTABLISHED')
    def test_output_guard_and_argument_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with self.assertRaises(ValueError):
                run_bounded(lambda *_:None,['--output-dir','evil'],p/'a',p/'b')
            with self.assertRaises(ValueError):
                run_bounded(lambda *_:None,['--coverage-cache','cache'],p/'a',p/'b',max_rounds=0)

if __name__ == '__main__':unittest.main()
