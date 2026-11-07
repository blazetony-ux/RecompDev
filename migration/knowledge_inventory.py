"""Read-only local SQLite inventory: never exports records, paths or SQL payloads."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

def inventory(path:Path):
    p=path.resolve(strict=True)
    if not p.is_file() or p.suffix.lower() not in {'.sqlite','.sqlite3','.db'}:
        raise ValueError('Not an approved SQLite catalogue')
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    # Read-only URI prevents writes; closing explicitly releases Windows file handles.
    with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Invalid catalogue')
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not r[0].startswith('sqlite_')]
        counts={t:db.execute('SELECT COUNT(*) FROM "'+t.replace('"','""')+'"').fetchone()[0] for t in tables}
    return {'schema':'recompdev.knowledge.inventory.v1','sha256':h,'bytes':p.stat().st_size,
            'table_rows':counts,'data_included':False,'modified':False}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('database',type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(inventory(args.database),sort_keys=True,indent=2))
if __name__=='__main__':main()
