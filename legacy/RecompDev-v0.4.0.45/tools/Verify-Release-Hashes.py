"""Verify every listed immutable release file against its manifest SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default='.')
    p.add_argument('--manifest',default='FILE_SHA256_v0413.json')
    args=p.parse_args()
    root=Path(args.root).resolve()
    manifest=(root/args.manifest).resolve()
    if root not in manifest.parents:raise ValueError('Manifest must be within release root')
    doc=json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(doc,dict) or not doc:raise ValueError('Manifest must contain file hashes')
    failures=[]
    for rel,expected in doc.items():
        if not isinstance(rel,str) or not isinstance(expected,str):raise ValueError('Invalid manifest entry')
        path=(root/rel).resolve()
        if root not in path.parents or len(expected)!=64 or path.is_symlink() or not path.is_file():
            failures.append(rel+': missing or invalid path');continue
        h=hashlib.sha256(path.read_bytes()).hexdigest()
        if h!=expected:failures.append(rel+': SHA-256 mismatch')
    if failures:
        for item in failures:print('FAILED',item)
        raise SystemExit(1)
    print('PASS:',len(doc),'release files match SHA-256 manifest')

if __name__=='__main__':main()
