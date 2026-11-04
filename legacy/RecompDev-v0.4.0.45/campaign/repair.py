"""Quarantined shared semantic recipe search with independent synthetic holdouts.

No source edits, no arbitrary code execution, no native function promotion. A
machine-readable recipe is committed only if discovery AND withheld fixtures
pass. Bad candidates are discarded, never patched into the running toolchain.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

SCHEMA='recomp-semantic-repair-experiment-v1'
RECIPES=('identity','bitwise-or','xor','wrapping-add')

def apply_recipe(recipe,a,b):
    if recipe=='identity':return a
    if recipe=='bitwise-or':return a|b
    if recipe=='xor':return a^b
    if recipe=='wrapping-add':return (a+b)&0xffffffff
    raise ValueError('Recipe not approved')

def parse_cases(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>1024*1024:
        raise ValueError('Missing or oversized fixture')
    content=p.read_bytes()
    doc=json.loads(content)
    if doc.get('schema')!='recomp-u32-reference-cases-v1' or doc.get('op')!='add-u32':
        raise ValueError('Unexpected independent reference fixture schema')
    cs=doc.get('cases')
    if not isinstance(cs,list) or not 2<=len(cs)<=500:raise ValueError('At least two bounded independent cases required')
    for c in cs:
        if set(c)!=set(('a','b','expected')) or any(type(c[k])!=int or not 0<=c[k]<=0xffffffff for k in c):
            raise ValueError('Invalid case')
    return cs,hashlib.sha256(content).hexdigest()

def trial(discovery,holdout,output,broken_recipe='bitwise-or'):
    if broken_recipe not in RECIPES:raise ValueError('Unknown baseline')
    cases,source_sha=parse_cases(discovery)
    secret,holdout_sha=parse_cases(holdout)
    if Path(discovery).resolve()==Path(holdout).resolve() or source_sha==holdout_sha:
        raise ValueError('Holdout must be an independent fixture')
    output=Path(output)
    if output.exists():raise ValueError('Refusing to overwrite committed semantic evidence')
    base_errors=sum(apply_recipe(broken_recipe,c['a'],c['b'])!=c['expected'] for c in cases)
    trials=[];selected=None
    for recipe in RECIPES:
        mismatches=sum(apply_recipe(recipe,c['a'],c['b'])!=c['expected'] for c in cases)
        held=sum(apply_recipe(recipe,c['a'],c['b'])!=c['expected'] for c in secret)
        trials.append({'recipe':recipe,'discovery_mismatches':mismatches,'holdout_mismatches':held})
        if selected is None and mismatches==0 and held==0:selected=recipe
    status='SYNTHETIC_RECIPE_VALIDATED' if selected and base_errors else 'BLOCKED_NO_VERIFIED_IMPROVEMENT'
    result={'schema':SCHEMA,'status':status,'operation':'add-u32','baseline':broken_recipe,
       'baseline_discovery_mismatches':base_errors,'selected_recipe':selected if status.startswith('SYNTHETIC') else None,
       'discovery_sha256':source_sha,'holdout_sha256':holdout_sha,
       'discovery_cases':len(cases),'holdout_cases':len(secret),'trials':trials,
       'source_edits':False,'runtime_semantics_modified':False,'native_qualified':False,
       'scope':'One restricted semantic recipe proven on synthetic reference vectors, not an automatic patch to a real compiler'}
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(output.suffix+'.tmp')
    try:
        temp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        temp.replace(output) # atomic publication after both fixture suites pass
    finally:
        if temp.exists():temp.unlink()
    return result
