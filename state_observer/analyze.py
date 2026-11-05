"""Hardware-independent read-only memory-change correlation.

The observer does not infer player addresses or game semantics. A supplied
input-state timeline is optional; absence of input yields unlabeled activity
statistics only. Provider identifiers, address spaces and byte orders come from
the trace, never from hard-coded CPU or machine rules.
"""
from __future__ import annotations
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

REGIONS_HEADER=['region_id','provider','address_space','base_address','size_bytes','byte_order','clock_domain']
DELTA_HEADER=['sample_seq','guest_frame','guest_cycle','region_id','offset','previous','current']
SUMMARY_HEADER=['region_id','samples','changes','truncated','truncate_reason']
MAX_EVENTS=2_000_000
MAX_REGIONS=64
MAX_REGION_BYTES=65_536

def _rows(path:Path,expected:list[str]):
    if not path.is_file():raise ValueError(f'Missing state-observer trace: {path.name}')
    with path.open(encoding='utf-8',newline='') as f:
        r=csv.DictReader(f)
        if r.fieldnames!=expected:raise ValueError(f'Invalid state-observer header: {path.name}')
        for row in r:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'Malformed state-observer row: {path.name}')
            yield row

def _number(value:str,name:str,lo=0,hi=(1<<63)-1):
    try:v=int(value)
    except (TypeError,ValueError):raise ValueError(f'Invalid {name}') from None
    if v<lo or v>hi:raise ValueError(f'Out-of-range {name}')
    return v

def _validate_regions(directory:Path):
    result={}
    for row in _rows(directory/'state-memory-regions.csv',REGIONS_HEADER):
        ident=row['region_id']
        if not ident or ident in result or len(result)>=MAX_REGIONS:
            raise ValueError('Duplicate/invalid observer region identifier')
        length=_number(row['size_bytes'],'size_bytes',1,MAX_REGION_BYTES)
        address=_number(row['base_address'],'base_address')
        if row['byte_order'] not in ('little','big','unknown'):
            raise ValueError('Invalid provider byte order')
        result[ident]={**row,'base_address':address,'size_bytes':length}
    if not result:raise ValueError('No observed memory regions')
    return result

def correlate(directory:Path, input_changes:list[dict]|None=None, input_clock_domain:str|None=None)->dict:
    """Read generic region/delta data and produce evidence, not player identity."""
    directory=Path(directory)
    regions=_validate_regions(directory)
    summaries={}
    for row in _rows(directory/'state-memory-summary.csv',SUMMARY_HEADER):
        rid=row['region_id']
        if rid not in regions or rid in summaries:raise ValueError('Unknown/duplicate summary region')
        summaries[rid]={
          'samples':_number(row['samples'],'samples',0,36000),
          'changes':_number(row['changes'],'changes',0,MAX_EVENTS),
          'truncated':bool(_number(row['truncated'],'truncated',0,1)),
          'truncate_reason':row['truncate_reason']}
    if set(regions)!=set(summaries):raise ValueError('Incomplete observer region summary')
    changes_per_addr=Counter()
    changed_frames=Counter()
    direction_counts=defaultdict(lambda:Counter())
    current={}  # only used to validate previous-value chaining, not to infer semantics
    region_rows=Counter()
    last_seq=-1;last_cycle_by_domain={};total=0
    inputs=list(input_changes or [])
    if any(a['guest_cycle']>b['guest_cycle'] for a,b in zip(inputs,inputs[1:])):
        raise ValueError('Out-of-order input cycle')
    input_index=0;state=0
    for row in _rows(directory/'state-memory-deltas.csv',DELTA_HEADER):
        if total>=MAX_EVENTS:raise ValueError('Observer event limit exceeded')
        seq=_number(row['sample_seq'],'sample_seq',0,35999)
        frame=_number(row['guest_frame'],'guest_frame')
        cycle=_number(row['guest_cycle'],'guest_cycle')
        rid=row['region_id']
        if rid not in regions:raise ValueError('Delta references unknown memory region')
        offset=_number(row['offset'],'offset',0,regions[rid]['size_bytes']-1)
        before=_number(row['previous'],'previous',-1,255)
        after=_number(row['current'],'current',0,255)
        domain=regions[rid]['clock_domain']
        if seq<last_seq or cycle<last_cycle_by_domain.get(domain,0):
            raise ValueError('Nonmonotonic memory observation')
        last_seq=seq;last_cycle_by_domain[domain]=cycle
        key=(rid,offset)
        old=current.get(key,-1)
        if before!=old:raise ValueError('Memory delta does not match preceding observation')
        if before>=0 and before==after:raise ValueError('No-op memory delta recorded')
        current[key]=after;total+=1;region_rows[rid]+=1
        if before>=0:
            changes_per_addr[key]+=1;changed_frames[frame]+=1
            if input_clock_domain is not None and domain==input_clock_domain:
                while input_index<len(inputs) and inputs[input_index]['guest_cycle']<=cycle:
                    state=inputs[input_index]['logical_buttons'];input_index+=1
                direction=state&0x0f
            else:
                direction=0
            if direction in (4,8):
                # Modular byte difference is only a statistical signal, NOT a world X value.
                step=((after-before+128)%256)-128
                if step:direction_counts[key][('left' if direction==4 else 'right','inc' if step>0 else 'dec')]+=1
    for rid,summary in summaries.items():
        if summary['changes']!=region_rows[rid]:raise ValueError('Observer summary count disagrees with changes')
    ranked=[]
    for (rid,off),count in changes_per_addr.most_common(80):
        directional=direction_counts[(rid,off)]
        left_up=directional[('left','inc')];left_down=directional[('left','dec')]
        right_up=directional[('right','inc')];right_down=directional[('right','dec')]
        score=(right_up-right_down)+(left_down-left_up)
        ranked.append({'region_id':rid,'offset':off,
                       'address':regions[rid]['base_address']+off,
                       'changes':count,
                       'left_increases':left_up,'left_decreases':left_down,
                       'right_increases':right_up,'right_decreases':right_down,
                       'directional_correlation_score':score})
    ranked.sort(key=lambda item:(-abs(item['directional_correlation_score']),-item['changes'],item['region_id'],item['offset']))
    result={
      'schema':'recompdev-state-observer-correlation-v1',
      'status':'TRUNCATED' if any(x['truncated'] for x in summaries.values()) else 'TRACE_COLLECTED',
      'regions':[dict(regions[k],**summaries[k]) for k in sorted(regions)],
      'observed_deltas':total,
      'changed_frame_count':len(changed_frames),
      'most_active_guest_frames':[{'guest_frame':f,'changes':n} for f,n in changed_frames.most_common(15)],
      'candidate_byte_offsets':ranked[:30],
      'candidate_interpretation':'UNIDENTIFIED_MEMORY_OFFSETS_NOT_PROVEN_PLAYER_COORDINATES',
      'input_correlation_clock_domain':input_clock_domain if inputs else None,
      'reference_emulator_parity':'NOT_TESTED',
      'host_mapping_or_guest_semantics':'NOT_DETERMINED_FROM_RAM_DIFFERENCES_ALONE',
      'sampling_note':'A provider-selected frame-boundary observation, not every guest memory write',
    }
    return result

def write_report(directory:Path,input_changes:list[dict]|None=None,input_clock_domain:str|None=None):
    directory=Path(directory)
    result=correlate(directory,input_changes,input_clock_domain)
    (directory/'state-memory-diagnostics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
