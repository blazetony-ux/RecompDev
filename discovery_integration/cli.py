"""Optional direct controller audit of an already completed discovery run.

The production controller calls bridge.audit automatically. This CLI supports
offline repetition from a saved report without touching a catalogue or ROM.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .bridge import audit


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True)
    p.add_argument('--working-catalogue',required=True)
    p.add_argument('--discovery-report',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--export-candidates',action='store_true')
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        info = audit(args.source,args.working_catalogue,args.discovery_report,args.output,
                     legacy_root=root/'legacy'/'RecompDev-v0.4.0.45',
                     export_candidates=args.export_candidates)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':f'{type(exc).__name__}: {exc}'},indent=2))
        return 2
    print(json.dumps(info,indent=2,sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
