"""Audit-only fast-forward preflight and independent verification for Git origin.

The release installer owns the actual Git push. This helper MUST NOT push,
create commits/tags, modify checkout source, or silently publish game history.
"""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path

class PublicationFailure(Exception):pass

def git(repo,*args,ok=True):
    result=subprocess.run(['git','-C',str(repo),*args],text=True,capture_output=True)
    if ok and result.returncode:
        raise PublicationFailure('GIT_COMMAND_FAILED: '+args[0]+' '+result.stderr.strip()[:400])
    return result

def _refs(repo,tag):
    result=git(repo,'ls-remote','origin','refs/heads/main','refs/tags/'+tag,'refs/tags/'+tag+'^{}')
    out={}
    for line in result.stdout.splitlines():
        parts=line.split()
        if len(parts)!=2 or not re.fullmatch('[0-9a-f]{40,64}',parts[0]):
            raise PublicationFailure('UNEXPECTED_GIT_REMOTE_REFERENCE')
        out[parts[1]]=parts[0]
    return out

def audit(repo:Path,tag:str,mode:str)->dict:
    if not re.fullmatch(r'workspace/v\d+\.\d+\.\d+\.\d+',tag):
        raise PublicationFailure('INVALID_RELEASE_TAG')
    if git(repo,'symbolic-ref','--short','HEAD').stdout.strip()!='main':
        raise PublicationFailure('PUBLICATION_REQUIRES_MAIN')
    if git(repo,'status','--porcelain','--untracked-files=all').stdout.strip():
        raise PublicationFailure('PUBLICATION_CHECKOUT_NOT_CLEAN')
    head=git(repo,'rev-parse','HEAD').stdout.strip()
    if git(repo,'rev-list','-n','1',tag).stdout.strip()!=head:
        raise PublicationFailure('RELEASE_TAG_NOT_ON_HEAD')
    refs=_refs(repo,tag)
    remote=refs.get('refs/heads/main')
    if mode=='preflight':
        if remote is None:raise PublicationFailure('ORIGIN_MAIN_MISSING')
        if 'refs/tags/'+tag in refs or 'refs/tags/'+tag+'^{}' in refs:
            raise PublicationFailure('ORIGIN_TAG_ALREADY_EXISTS')
        # Fetch precisely the branch, not all refs, without modifying main.
        git(repo,'fetch','--no-tags','origin','refs/heads/main')
        fetched=git(repo,'rev-parse','FETCH_HEAD').stdout.strip()
        if fetched!=remote:raise PublicationFailure('ORIGIN_MAIN_CHANGED_DURING_PREFLIGHT')
        if git(repo,'merge-base','--is-ancestor',fetched,head,ok=False).returncode!=0:
            raise PublicationFailure('ORIGIN_MAIN_NOT_ANCESTOR_REFUSE_NON_FAST_FORWARD')
        return {'schema':'recompdev.origin-publication.v1','status':'SAFE_FAST_FORWARD',
                'release_tag':tag,'local_main':head,'remote_main_before':remote,
                'push_executed_by_helper':False}
    if mode=='verify':
        peeled=refs.get('refs/tags/'+tag+'^{}',refs.get('refs/tags/'+tag))
        if remote!=head or peeled!=head:
            raise PublicationFailure('ORIGIN_MAIN_OR_TAG_VERIFICATION_MISMATCH')
        return {'schema':'recompdev.origin-publication.v1','status':'VERIFIED',
                'release_tag':tag,'local_main':head,'remote_main_after':remote,
                'push_executed_by_helper':False}
    raise PublicationFailure('UNKNOWN_AUDIT_MODE')

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['preflight','verify'])
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--tag',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    try:
        result=audit(a.repo,a.tag,a.mode)
        if a.out.exists() and a.mode=='preflight':raise PublicationFailure('PUBLICATION_EVIDENCE_EXISTS')
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf8')
        print('RECOMPDEV_ORIGIN_AUDIT='+json.dumps(result,sort_keys=True))
        return 0
    except (OSError,PublicationFailure) as e:
        print('RECOMPDEV_ORIGIN_AUDIT_ERROR='+str(e),file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
