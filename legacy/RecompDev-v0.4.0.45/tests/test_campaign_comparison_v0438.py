import unittest
from nativecore.campaign_compare_v0438 import compare_campaign

def campaign(rom='same',frames=66,steps=2_000_000,recs=6,status='RAM_EXECUTION_NOT_TRANSLATED'):
 return {'release':'0.4.0.38','frames_requested':120,'steps_requested':steps,'max_recoveries':recs,
         'games':[{'slug':'alex','sha256':rom,'maximum_frames_observed':frames,'status':status}]}

class CampaignComparison438(unittest.TestCase):
 def test_progress_and_regression_never_claim_cpu_parity(self):
  before=campaign(frames=66);before['baseline_release']='0.4.0.36'
  good=compare_campaign(before,campaign(frames=100))
  self.assertEqual(good['games'][0]['assessment'],'FRAME_PROGRESS_NOT_PARITY')
  self.assertEqual(good['cpu_parity'],'NOT_TESTED')
  bad=compare_campaign(before,campaign(frames=61))
  self.assertEqual(bad['games'][0]['assessment'],'FRAME_REGRESSION_OBSERVED')
 def test_mismatch_budget_and_missing_evidence(self):
  before=campaign()
  self.assertEqual(compare_campaign(before,campaign(rom='other'))['games'][0]['assessment'],'SOURCE_IDENTITY_MISMATCH')
  self.assertEqual(compare_campaign(before,campaign(recs=9))['games'][0]['assessment'],'BUDGETS_DIFFER_COMPARISON_UNQUALIFIED')
  self.assertEqual(compare_campaign(before,{'release':'x','games':[]})['games'][0]['assessment'],'NO_PAIRED_RUN')
 def test_real_baseline_has_all_seven_identities(self):
  from pathlib import Path
  import json
  root=Path(__file__).resolve().parents[1]
  data=json.loads((root/'evidence/baselines/sms-seven-v0436.json').read_text())
  self.assertEqual(len(data['games']),7)
  self.assertEqual(len({g['sha256'] for g in data['games']}),7)
  for game in data['games']:
   self.assertEqual(len(game['sha256']),64)
if __name__=='__main__':unittest.main()
