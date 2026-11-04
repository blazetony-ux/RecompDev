"""Safeguard against claiming Shinobi CPU divergence from unaligned selected I/O."""
import json,tempfile,unittest
from pathlib import Path
from nativecore.hardware_triage_v0435 import diagnose

class HardwareTriage435(unittest.TestCase):
 def test_reference_unaligned_and_cram_zero_stays_unqualified(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);pilot=root/'pilot.json';align=root/'alignment.json'
   source='a'*64
   pilot.write_text(json.dumps({'source_id':source,'recovery_attempts':[],
      'dependency_frontier':[{'branch':'unresolved'}],
      'trace':{'native_steps':703381,'status':'STEP_BUDGET_REACHED','cram_nonzero_bytes':0,
               'vblank_events':120,'maskable_interrupts':0,
               'checkpoints':[{'step':0,'pc':0,'mapper':[0,0,1,2]}]}}))
   align.write_text(json.dumps({'source_sha256':source,'same_initial_machine_state_proven':False,
     'cpu_instruction_boundaries_aligned':False,'frame_phase_aligned':False,
     'first_selected_io_difference':{'bus_index':0}}))
   got=diagnose(pilot,align)
   self.assertEqual(got['reference_alignment'],'UNALIGNED')
   self.assertEqual(got['root_cause'],'NOT_ESTABLISHED')
   self.assertFalse(got['native_qualified'])
   self.assertIn('TRACE_FIRST_EXPECTED_CRAM_INITIALIZATION_AND_PRECEDING_VDP_COMMANDS',got['diagnostic_priorities'])
   self.assertEqual(got['first_reference_difference']['bus_index'],0)
   claim=json.loads(align.read_text())
   for key in ('same_initial_machine_state_proven','cpu_instruction_boundaries_aligned','frame_phase_aligned'):claim[key]=True
   align.write_text(json.dumps(claim))
   self.assertEqual(diagnose(pilot,align)['reference_alignment'],'REPORTED_ALIGNED_UNVERIFIED')
   self.assertEqual(diagnose(pilot,align)['root_cause'],'NOT_ESTABLISHED')
   align.write_text(align.read_text().replace(source,'b'*64))
   with self.assertRaisesRegex(ValueError,'source differs'):diagnose(pilot,align)
if __name__=='__main__':unittest.main()
