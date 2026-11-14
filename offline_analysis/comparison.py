"""Provider-neutral release-to-release ROM discovery audit.

Compares *attested decode candidates*, never asserts semantic coverage.
Unsupported classifications and speculative reachability remain distinct.
"""
from __future__ import annotations
import collections,hashlib,json
from pathlib import Path
from offline_analysis.engine import AnalysisFailure

def _sha(b):return hashlib.sha256(b).hexdigest()
def read_previous(location:Path,source_hash:str):
    d=Path(location).absolute()
    if d.is_symlink() or not d.is_dir():raise AnalysisFailure('COMPARISON_BASELINE_DIRECTORY_INVALID')
    receipt=d/'analysis.json'
    if receipt.is_symlink() or not receipt.is_file():raise AnalysisFailure('COMPARISON_BASELINE_RECEIPT_MISSING')
    r=json.loads(receipt.read_text(encoding='utf8'))
    if r.get('schema')!='recompdev.offline.analysis.v1' or r.get('source_sha256')!=source_hash:
        raise AnalysisFailure('COMPARISON_SOURCE_HASH_OR_SCHEMA_MISMATCH')
    prior=r.get('artifacts',{}).get('instructions.json')
    path=d/'instructions.json'
    if prior is None or path.is_symlink() or not path.is_file():
        raise AnalysisFailure('COMPARISON_INSTRUCTION_RECEIPT_MISSING')
    raw=path.read_bytes()
    if _sha(raw)!=prior.get('sha256') or len(raw)!=prior.get('bytes'):
        raise AnalysisFailure('COMPARISON_INSTRUCTION_RECEIPT_TAMPERED')
    return r,json.loads(raw)

def compare(previous:Path,source_sha256:str,now:list,now_gaps:list)->dict:
    prior,old=read_previous(previous,source_sha256)
    def ident(x):return (x['pc'],x['physical'],x['length'],x['bytes_sha256'])
    aa={ident(x):x for x in old};bb={ident(x):x for x in now}
    oldonly=sorted(aa.keys()-bb.keys());newonly=sorted(bb.keys()-aa.keys())
    revised=sorted(k for k in aa.keys()&bb.keys() if aa[k]['classification']!=bb[k]['classification'])
    # Never imply that more entries is better code coverage.
    return {'schema':'recompdev.offline.regression-comparison.v1',
        'source_sha256':source_sha256,'baseline_release':prior.get('release'),
        'baseline_candidates':len(old),'current_candidates':len(now),
        'retained':len(aa.keys()&bb.keys()),'new_candidates':len(newonly),
        'missing_candidates':len(oldonly),'reclassified':len(revised),
        'new_candidate_sites':[{'pc':k[0],'physical':k[1]} for k in newonly],
        'missing_candidate_sites':[{'pc':k[0],'physical':k[1]} for k in oldonly],
        'classification_changes':[{'pc':k[0],'physical':k[1],
                                  'before':aa[k]['classification'],'after':bb[k]['classification']}
                                 for k in revised],
        'unresolved_current':len(now_gaps),'unresolved_baseline':prior.get('unresolved'),
        'semantic_coverage_increase_proven':False,'gameplay_qualified':False}
