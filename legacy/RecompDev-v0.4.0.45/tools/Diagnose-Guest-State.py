#!/usr/bin/env python3
"""Summarise guest hardware events and selected RAM writer provenance."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nativecore.state_dependency import analyze_event_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', required=True, help='Glob matching ordered event chunks')
    parser.add_argument('--source-sha256', help='Optional authenticated identity from upstream evidence')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    glob = Path(args.events)
    files = sorted(glob.parent.glob(glob.name))
    out = Path(args.output).resolve()
    if out.exists():
        parser.error('Refusing to overwrite existing diagnostic evidence')
    try:
        report = analyze_event_files(files, args.source_sha256)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        parser.error(str(e))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('DIAGNOSTIC_REPORT=' + str(out))
    print('OBSERVED_CRAM_WRITES=' + str(report['cram']['writes']))
    print('WATCHED_RAM_ADDRESSES=' + str(len(report['watched_ram'])))
    print('PARITY=' + report['reference_equivalence'])


if __name__ == '__main__':
    main()
