import json
import tempfile
import unittest
from pathlib import Path
from nativecore.state_dependency import analyze_event_files

class StateDependencyDevelopmentTests(unittest.TestCase):
    def test_selected_ram_writes_and_palette_provenance(self):
        events = [
            {'step': 3, 'pc': 0x1082, 'kind': 'CRAM_WRITE', 'address': 0, 'value': 0},
            {'step': 5, 'pc': 0x0FE7, 'kind': 'IRQ', 'address': 0x38, 'value': 1},
            {'step': 6, 'pc': 0x0FE7, 'kind': 'RAM_WATCH_WRITE', 'address': 0xC001, 'value': 1},
            {'step': 9, 'pc': 0x0BF6, 'kind': 'RAM_WATCH_WRITE', 'address': 0xC001, 'value': 0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'events-000000.jsonl'
            p.write_text(''.join(json.dumps(e)+'\n' for e in events))
            report = analyze_event_files([p], 'a'*64)
            self.assertIn('OBSERVED_CRAM_WRITES_ALL_ZERO', report['findings'])
            self.assertEqual(report['cram']['writer_pcs'], [{'value':'0x1082','count':1}])
            self.assertEqual(report['watched_ram']['0xC001']['writer_pcs'], [
                {'value':'0x0BF6','count':1},{'value':'0x0FE7','count':1}])
            self.assertEqual(report['reference_equivalence'],'NOT_ESTABLISHED')

    def test_nonmonotonic_and_missing_ram_evidence_fail_conservatively(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'events.jsonl'
            p.write_text(json.dumps({'step':2,'pc':1,'kind':'CRAM_WRITE','address':1,'value':7})+'\n')
            summary=analyze_event_files([p])
            self.assertIn('RAM_WRITER_PROVENANCE_NOT_CAPTURED',summary['findings'])
            self.assertNotIn('OBSERVED_CRAM_WRITES_ALL_ZERO',summary['findings'])
            with p.open('a') as f:
                f.write(json.dumps({'step':1,'pc':1,'kind':'IRQ','address':56,'value':1})+'\n')
            with self.assertRaisesRegex(ValueError,'Nonmonotonic'):
                analyze_event_files([p])

if __name__=='__main__': unittest.main()
