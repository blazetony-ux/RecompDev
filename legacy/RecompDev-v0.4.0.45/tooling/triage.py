"""Deterministic, architecture-independent evidence decision planner.

Never guesses instruction semantics, changes original files or patches generated code.
The output is an evidence request, not proof of a repaired defect.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def decide(evidence):
    status=evidence.get('status')
    stage=evidence.get('verification') if isinstance(evidence.get('verification'),dict) else {}
    if status in ('SELECTED_IO_DIVERGED','DIVERGED') and any(evidence.get(k) is False for k in ('pc_aligned','step_aligned','frame_aligned')):
        next_step='CAPTURE_COMMON_BOOT_SOURCE_AND_RESET_ANCHOR'
        reason='Divergence is unaligned; ordinal event equality does not imply shared execution state'
        gate='BLOCKED_NO_COMPARABLE_START_STATE'
    elif status in ('ANALYSIS_RECONCILED','SINGLE_ENGINE_ONLY'):
        if status=='SINGLE_ENGINE_ONLY':
            next_step='RUN_INDEPENDENT_SECOND_STATIC_ANALYZER';reason='Only one boundary hypothesis exists'
        else:
            next_step='VERIFY_INSTRUCTION_BYTES_AND_DYNAMIC_EDGES';reason='Function boundary agreement is not execution semantics'
        gate='BLOCKED_NO_RUNTIME_PARITY'
    elif status in ('DIVERGED','SELECTED_IO_DIVERGED'):
        next_step='CAPTURE_FIRST_MATCHED_CPU_STATE_AND_BUS_EFFECTS';reason='Comparable execution context needs independent instruction/state observations'
        gate='BLOCKED_DIAGNOSTIC_ONLY'
    else:
        next_step='ESTABLISH_SOURCE_ATTESTED_TOOL_EVIDENCE';reason='No independently usable verification evidence supplied'
        gate='BLOCKED_MISSING_EVIDENCE'
    return {'schema':'recomp-investigation-plan-v1','input_status':status or 'UNKNOWN',
      'next_action':next_step,'reason':reason,'promotion_gate':gate,'automatic_source_edit':False,
      'independent_verification':'NOT_ESTABLISHED','native_parity':stage.get('native_parity','NOT_TESTED')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    f=Path(args.evidence)
    if not f.is_file() or f.stat().st_size>2*1024*1024:raise ValueError('Missing/oversized evidence')
    plan=decide(json.loads(f.read_text(encoding='utf-8')))
    out=Path(args.output)
    if out.exists():raise ValueError('Existing plan will not be overwritten')
    out.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8');print(json.dumps(plan,indent=2))
if __name__=='__main__':main()
