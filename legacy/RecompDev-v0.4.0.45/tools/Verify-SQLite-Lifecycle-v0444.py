#!/usr/bin/env python3
"""Fail closed on the SQLite connection context-manager trap.

`with sqlite3.connect(...)` commits/rolls back, but does NOT close the
connection. Windows holds the file open, preventing TemporaryDirectory cleanup.
Use `with closing(sqlite3.connect(...)) as con, con:` for write transactions
or `with closing(sqlite3.connect(...)) as con:` for reads.
"""
import ast
import argparse
from pathlib import Path


def find_unsafe(source, filename="<memory>"):
    tree = ast.parse(source, filename=filename)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                expr = item.context_expr
                if (isinstance(expr, ast.Call)
                        and isinstance(expr.func, ast.Attribute)
                        and expr.func.attr == "connect"
                        and isinstance(expr.func.value, ast.Name)
                        and expr.func.value.id == "sqlite3"):
                    found.append((filename, expr.lineno))
    return found


def scan(root):
    root=Path(root)
    if not (root/'RELEASE_VERSION').is_file():
        raise ValueError('Expected real release directory')
    failures=[]
    for source in sorted(root.rglob('*.py')):
        if any(p in ('__pycache__','evidence','.git') for p in source.relative_to(root).parts):continue
        failures.extend(find_unsafe(source.read_text(encoding='utf-8'),str(source.relative_to(root))))
    return failures


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,required=True)
    a=ap.parse_args()
    failures=scan(a.root)
    if failures:
        for filename,lineno in failures:print(f'FAIL: sqlite3.connect without close at {filename}:{lineno}')
        raise SystemExit(1)
    print('PASS: SQLite connection lifecycle preflight (no direct sqlite3.connect context managers)')

if __name__=='__main__':main()
