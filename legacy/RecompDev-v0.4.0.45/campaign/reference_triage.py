"""Evidence-driven, fail-closed next action for external selected-bus comparisons.

This diagnostic may explain WHY an apparent first difference is not yet
qualifiable. No heuristic event skipping, gameplay parity or source edits.
"""
import hashlib,json
from pathlib import Path
SCHEMA='recomp-reference-investigation-v0421'

def triage(source,comparison,output):
    source=Path(source).resolve(strict=True)
    comparison=Path(comparison).resolve(strict=True)
    if not comparison.is_file() or comparison.is_symlink() or comparison.stat().st_size>2*1024*1024:
        raise ValueError('Missing/oversized comparison')
    doc=json.loads(comparison.read_text(encoding='utf-8'))
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if doc.get('schema')!='recomp-mame-sms-bus-comparison-v1' or doc.get('source_sha256')!=sha:
        raise ValueError('External comparison source identity mismatch')
    for name in ('reference_writes','native_writes','matching_prefix_writes'):
        if type(doc.get(name))!=int or doc[name]<0:raise ValueError('Malformed ordered event count')
    if doc['matching_prefix_writes']>min(doc['reference_writes'],doc['native_writes']):
        raise ValueError('Impossible matching prefix')
    aligned=all(doc.get(x) is True for x in ('pc_aligned','step_aligned','frame_aligned'))
    if not aligned:
        status='BLOCKED_UNALIGNED_EXECUTIONS'
        action='ACQUIRE_AUTHENTICATED_BOOT_MAPPING_AND_COMMON_CPU_STATE'
        suspect='REFERENCE_STARTUP_OR_BOOT_CONFIGURATION'
    elif doc['status']=='SELECTED_IO_DIVERGED':
        status='DIAGNOSTIC_DIVERGENCE_NEEDS_CPU_AND_CYCLE_EVIDENCE'
        action='CAPTURE_ALIGNED_INSTRUCTION_AND_MAPPER_BOUNDARY_TRACE'
        suspect=(doc.get('first_divergence') or {}).get('native',{}).get('kind','UNKNOWN')
    else:
        status='INCOMPLETE_SELECTED_IO_SCOPE'
        action='CAPTURE_FULL_INDEPENDENT_CPU_AND_HARDWARE_EFFECTS'
        suspect='NOT_LOCALIZED'
    first=doc.get('first_divergence')
    if first is not None and (not isinstance(first,dict) or type(first.get('bus_index'))!=int
                              or first['bus_index']<0):raise ValueError('Malformed divergence record')
    result={'schema':SCHEMA,'status':status,'next_action':action,'suspected_area':suspect,
            'source_sha256':sha,'comparison_sha256':hashlib.sha256(comparison.read_bytes()).hexdigest(),
            'reference_writes':doc['reference_writes'],'native_writes':doc['native_writes'],
            'matching_prefix_writes':doc['matching_prefix_writes'],
            'first_selected_difference':first['bus_index'] if first else None,
            'strict_ordinal_matching_only':True,'automatic_repair':False,
            'native_qualified':False,'gameplay_parity':'NOT_ESTABLISHED',
            'note':'No event-prefix offset may be inferred without independently authenticated execution alignment'}
    output=Path(output)
    if output.exists():raise ValueError('Immutable investigation evidence exists')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result
