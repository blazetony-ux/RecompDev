"""v23 source-independent display decimation and watch-summary evidence."""
import unittest
from pathlib import Path
from execution_monitor.stream import LiveDisplaySampler
from execution_monitor.job_preview import safe_excerpt
from controller.diagnostics import normalize

class V23Telemetry(unittest.TestCase):
    def test_display_decimation_never_discards_critical_events(self):
        sent=[]
        sampler=LiveDisplaySampler(sent.append,instruction_interval=16)
        for index in range(1600):
            sampler({'type':'instruction','cpu':'generic','steps':index,'watch_hit':True})
        for kind in ('frame','input','stop','watch_summary','notice'):
            sampler({'type':kind})
        self.assertEqual(sampler.seen_instructions,1600)
        self.assertEqual(sampler.suppressed_instructions,1500)
        self.assertEqual(sampler.forwarded_events,105)
        self.assertEqual([item['type'] for item in sent[-5:]],
                         ['frame','input','stop','watch_summary','notice'])

    def test_summary_protocol_and_sanitized_evidence(self):
        event={'type':'watch_summary','pc':123,'hit_count':4096,
               'hits_total':8192,'coalesced_hits':8000,
               'unbucketed_hits':0,'final':True,'private':'do-not-publish'}
        row=normalize(event)
        self.assertEqual(row['type'],'watch_summary')
        excerpt=safe_excerpt(row)
        self.assertNotIn('private',excerpt)
        self.assertEqual(excerpt['hits_total'],8192)
        self.assertTrue(excerpt['final'])

    def test_source_does_not_modify_native_machine_or_templates(self):
        root=Path(__file__).resolve().parents[2]
        source=(root/'execution_monitor/bridge/rd_execution_events.hpp').read_text()
        self.assertIn('kWatchSummaryStride=4096',source)
        self.assertIn('kInstructionEventCeiling=180000',source)
        self.assertIn('coalesced_hits_',source)
        self.assertNotIn('shinobi',source.lower())
        preview=(root/'execution_monitor/job_preview.py').read_text()
        self.assertIn('LiveDisplaySampler(broker.publish',preview)
        self.assertIn('Publisher::instance().finish()',preview)

if __name__=='__main__':unittest.main()
