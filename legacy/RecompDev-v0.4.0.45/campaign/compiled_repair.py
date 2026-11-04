"""Automated synthetic correction -> generated C++ -> independent holdout execution.

An isolated proof-of-mechanism. No patch to CPU generators or live runtime.
Discovery vectors select a candidate; holdouts only verify that candidate.
On failure no approved recipe is published or used by production components.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import re
import subprocess
from campaign.repair import parse_cases, RECIPES, apply_recipe

EXPR={'identity':'a', 'bitwise-or':'(a|b)', 'xor':'(a^b)', 'wrapping-add':'(a+b)'}
SCHEMA='recomp-compiled-synthetic-repair-v0421'

def repair(train,holdout,output,compiler,baseline='bitwise-or'):
    if baseline not in RECIPES:raise ValueError('Unknown bounded baseline recipe')
    train=Path(train).resolve(strict=True);holdout=Path(holdout).resolve(strict=True)
    if train==holdout:raise ValueError('Independent holdout required')
    a,ash=parse_cases(train);b,bsh=parse_cases(holdout)
    if ash==bsh:raise ValueError('Identical discovery and holdout not independent')
    compiler=Path(compiler).resolve(strict=True)
    if not compiler.is_file() or not re.fullmatch(r'(?:[a-z0-9_+-]*-)?(?:g\+\+|clang\+\+)(?:-\d+)?',compiler.name.lower()):
        raise ValueError('Only explicitly specified g++ or clang++ supported for this experiment')
    output=Path(output).resolve()
    if output.exists():raise ValueError('Immutable repair experiment exists')
    output.mkdir(parents=True,exist_ok=False)
    baseline_bad=sum(apply_recipe(baseline,c['a'],c['b'])!=c['expected'] for c in a)
    candidates=[recipe for recipe in RECIPES if all(apply_recipe(recipe,c['a'],c['b'])==c['expected'] for c in a)]
    result={'schema':SCHEMA,'source_sha256':ash,'independent_holdout_sha256':bsh,
            'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),
            'baseline':baseline,'baseline_failures':baseline_bad,'discovery_candidates':candidates,
            'selected':None,'status':'BLOCKED_NO_DISCOVERY_SOLUTION','production_patched':False,
            'native_qualified':False,'gameplay':'NOT_ESTABLISHED','dependent_test_retried':False}
    try:
        if baseline_bad and len(candidates)==1:
            choice=candidates[0]
            # Generate a new isolated native executable that checks the holdout
            # vectors at runtime. The compiler does not execute source from
            # an external ROM, only the fixed allowlisted expression.
            lines=['#include <cstdint>','int main() {','  unsigned failures=0;']
            for c in b:
                lines.append(f"  {{ uint32_t a={c['a']}u,b={c['b']}u; if(uint32_t({EXPR[choice]})!={c['expected']}u) ++failures; }}")
            lines.extend(['  return failures==0 ? 0 : 5;','}'])
            cpp=output/'candidate.cpp';cpp.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            exe=output/'candidate.exe' if __import__('os').name=='nt' else output/'candidate'
            proc=subprocess.run([str(compiler),'-std=c++17','-O2',str(cpp),'-o',str(exe)],
                                 capture_output=True,text=True,timeout=40)
            (output/'compiler.log').write_text((proc.stdout+proc.stderr)[-12000:],encoding='utf-8')
            if proc.returncode or not exe.is_file():
                result['status']='BLOCKED_COMPILER_FAILURE'
            else:
                executed=subprocess.run([str(exe)],capture_output=True,text=True,timeout=8)
                result['dependent_test_retried']=True
                result['native_executable_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
                result['status']='ISOLATED_COMPILED_HOLDOUT_PASS' if executed.returncode==0 else 'REJECTED_HOLDOUT_DIVERGENCE'
                if executed.returncode==0:
                    result['selected']=choice
                    # A verified recipe *candidate*, not a production patch.
                    (output/'verified-quarantined-recipe.json').write_text(json.dumps({
                         'schema':'recomp-quarantined-recipe-v0421','recipe':choice,
                         'discovery_sha256':ash,'holdout_sha256':bsh,
                         'native_executable_sha256':result['native_executable_sha256'],
                         'production_patch_approved':False},indent=2)+'\n',encoding='utf-8')
        elif not baseline_bad:result['status']='BLOCKED_NO_BASELINE_FAILURE'
        elif len(candidates)>1:result['status']='BLOCKED_AMBIGUOUS_DISCOVERY'
    except (subprocess.TimeoutExpired,OSError) as exc:
        result['status']='BLOCKED_COMPILATION_OR_EXECUTION'
        result['error']=type(exc).__name__
    result['source_unchanged']=hashlib.sha256(train.read_bytes()).hexdigest()==ash
    result['holdout_unchanged']=hashlib.sha256(holdout.read_bytes()).hexdigest()==bsh
    if not result['source_unchanged'] or not result['holdout_unchanged']:
        result['status']='BLOCKED_EVIDENCE_CHANGED';result['selected']=None
        (output/'verified-quarantined-recipe.json').unlink(missing_ok=True)
    (output/'repair-report.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result
