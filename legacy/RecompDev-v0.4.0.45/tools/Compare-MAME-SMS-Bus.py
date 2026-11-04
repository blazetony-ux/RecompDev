"""Compare owner-run MAME selected I/O writes with native SHA-verified event chunks.
Not an instruction-level or frame parity claim. No repairs are applied.
"""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.bus_oracle import compare_bus

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-dir',required=True)
    p.add_argument('--pilot-report',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    reference=Path(a.reference_dir).resolve();pilot=Path(a.pilot_report).resolve();out=Path(a.output).resolve()
    if out.exists():p.error('Output already exists; immutable comparison required')
    manifest=reference/'selected-bus-reference.json';bus=reference/'mame-bus.jsonl'
    if any(not path.is_file() or path.stat().st_size>32*1024*1024 for path in (manifest,bus,pilot)):
        p.error('Missing/oversized evidence')
    ref=json.loads(manifest.read_text(encoding='utf-8'))
    candidate=json.loads(pilot.read_text(encoding='utf-8'))
    trace=candidate.get('trace') or candidate
    rel=trace.get('event_stream_directory')
    if not isinstance(rel,str) or not re.fullmatch(r'event-streams/attempt-\d{2}-budget-\d{1,7}',rel):
        p.error('Invalid candidate event stream directory')
    diagnosis=compare_bus(ref,bus,candidate,pilot.parent/rel)
    out.write_text(json.dumps(diagnosis,indent=2)+'\n',encoding='utf-8')
    print(diagnosis['status'],'--',diagnosis['matching_prefix_writes'],'selected I/O writes matched')
    print('Report:',out)
    raise SystemExit(1 if diagnosis['status']=='SELECTED_IO_DIVERGED' else 0)
if __name__=='__main__':main()
