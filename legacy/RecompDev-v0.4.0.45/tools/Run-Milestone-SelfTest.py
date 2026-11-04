#!/usr/bin/env python3
"""Self-contained real native compile on an author-created non-game 68000 program."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign.engine import run

def main():
    compiler=shutil.which('cmake') or shutil.which('g++') or shutil.which('clang++') or shutil.which('cl.exe')
    if not compiler:
        print(json.dumps({'status':'BLOCKED_COMPILER_NOT_INSTALLED','action':'Install a supported host C++ compiler'}))
        return 2
    with tempfile.TemporaryDirectory(prefix='recompdev-v0420-selftest-') as work:
        root=Path(work);source=root/'synthetic-m68k.bin'
        source.write_bytes(bytes.fromhex('7001528053804e75'))
        report=run(source,root/'campaign','m68k',synthetic=True,compiler=compiler)
        summary={'status':report['status'],'second_isa':report['release_milestones']['second_isa'],
            'source_unchanged':report['source_unchanged'],'native_qualified':report['native_qualified'],
            'gameplay':report['gameplay']}
        print(json.dumps(summary,indent=2))
        return 0 if summary['second_isa']=='RESTRICTED_FIXTURE_PASS' else 2
if __name__=='__main__':raise SystemExit(main())
