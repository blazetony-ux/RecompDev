#!/usr/bin/env python3
"""Fail closed if a release verification pattern selects no runnable tests."""
import argparse
import sys
import unittest
from pathlib import Path


def count_discovered(folder, pattern):
    folder=Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError(f'Fixture directory missing: {folder}')
    matches=list(folder.glob(pattern))
    if not matches or not all(p.is_file() for p in matches):
        raise ValueError(f'Missing regression file for {pattern}: {folder}')
    release_root=str(Path(__file__).resolve().parents[1])
    if release_root not in sys.path:sys.path.insert(0,release_root)
    loader=unittest.TestLoader()
    suite=loader.discover(start_dir=str(folder),pattern=pattern,top_level_dir=str(folder))
    if loader.errors:
        raise ValueError(f'Import or discovery errors for {pattern}: {loader.errors[0][:500]}')
    result=suite.countTestCases()
    if result==0:
        raise ValueError(f'Zero tests discovered for {pattern}: {folder}')
    return result


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--folder',required=True)
    ap.add_argument('--patterns',nargs='+',required=True)
    a=ap.parse_args(argv)
    try:
        for pattern in a.patterns:
            n=count_discovered(a.folder,pattern)
            print(f'DISCOVERY_PASS: {pattern}: {n} test(s)',flush=True)
    except (OSError,ValueError,ImportError) as exc:
        print(f'DISCOVERY_FAILED: {exc}',file=sys.stderr,flush=True)
        return 1
    return 0

if __name__=='__main__':sys.exit(main())
