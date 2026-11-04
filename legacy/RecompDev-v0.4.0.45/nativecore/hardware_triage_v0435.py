"""Conservative source-bound Z80/SMS native runtime and reference triage.

Reports observed CPU/IRQ/mapper/CRAM states and unaligned reference differences.
Does not invent checkpoints or turn bus differences into proven CPU defects.
"""
import json
from pathlib import Path
from nativepilot.generator import sha256

def diagnose(pilot_report, alignment_report=None):
    file=Path(pilot_report).resolve(strict=True)
    if not file.is_file() or file.stat().st_size>4*1024*1024:raise ValueError('Pilot report missing or oversized')
    report=json.loads(file.read_text(encoding='utf-8'))
    source=report.get('source_id')
    if not isinstance(source,str) or len(source)!=64 or any(c not in '0123456789abcdef' for c in source):
        raise ValueError('Invalid source identity')
    trace=report.get('trace') or {}
    if not isinstance(trace,dict):raise ValueError('Invalid pilot trace')
    cps=trace.get('checkpoints',[])
    if not isinstance(cps,list) or len(cps)>10000:raise ValueError('Unbounded CPU checkpoints')
    snapshots=[]
    for point in cps[:16]:
        if not isinstance(point,dict):raise ValueError('Invalid CPU checkpoint')
        snapshots.append({key:point.get(key) for key in
            ('step','pc','af','bc','de','hl','sp','mapper','tstates','frames','irqs','ram_writes','vram_writes','cram_writes','psg_writes')})
    frontier=report.get('dependency_frontier') or []
    if not isinstance(frontier,list):frontier=[]
    summary={'schema':'recomp-sms-hardware-triage-v0435','source_sha256':source,
       'pilot_report_sha256':sha256(file),'native_status':trace.get('status',report.get('status')),
       'native_steps':trace.get('native_steps'),
       'rom_pc':trace.get('pc'),'mapper':trace.get('mapper'),
       'cpu_snapshots':snapshots,'last_pcs':trace.get('last_pcs',[])[:24],
       'unresolved_dependency_frontier':frontier[:12],
       'vdp':{'control_writes':trace.get('vdp_control_writes'),
              'data_writes':trace.get('vdp_data_writes'),
              'cram_writes':trace.get('cram_writes'),
              'cram_nonzero_bytes':trace.get('cram_nonzero_bytes'),
              'vram_nonzero_bytes':trace.get('vram_nonzero_bytes')},
       'interrupts':{'vblank_events':trace.get('vblank_events'),
                     'maskable_interrupts':trace.get('maskable_interrupts')},
       'recovery_attempt_count':len(report.get('recovery_attempts',[])),
       'reference_alignment':'NOT_PROVIDED','first_reference_difference':None,
       'diagnostic_priorities':[],
       'root_cause':'NOT_ESTABLISHED','native_qualified':False,'gameplay':'NOT_ESTABLISHED'}
    if alignment_report:
        path=Path(alignment_report).resolve(strict=True)
        if path.stat().st_size>4*1024*1024:raise ValueError('Alignment report oversized')
        reference=json.loads(path.read_text(encoding='utf-8'))
        if reference.get('source_sha256')!=source:raise ValueError('Reference source differs from pilot')
        summary['alignment_report_sha256']=sha256(path)
        summary['reference_alignment']='REPORTED_ALIGNED_UNVERIFIED' if all(reference.get(k) is True for k in
            ('same_initial_machine_state_proven','cpu_instruction_boundaries_aligned','frame_phase_aligned')) else 'UNALIGNED'
        summary['first_reference_difference']=reference.get('first_selected_io_difference')
    if summary['reference_alignment']=='UNALIGNED':
        summary['diagnostic_priorities'] += [
           'ALIGN_MAME_BOOT_PATH_AND_CPU_RESET_STATE_BEFORE_ASSIGNING_CAUSE',
           'COLLECT_MAME_AND_NATIVE_PC_REGISTER_MAPPER_IRQ_CHECKPOINTS_AT_MATCHED_INSTRUCTION_BOUNDARIES']
    if trace.get('cram_nonzero_bytes')==0:
        summary['diagnostic_priorities'].append('TRACE_FIRST_EXPECTED_CRAM_INITIALIZATION_AND_PRECEDING_VDP_COMMANDS')
    if trace.get('vblank_events',0)>0 and trace.get('maskable_interrupts',0)==0:
        summary['diagnostic_priorities'].append('CHECK_IFF_IRQ_ENABLE_AND_VDP_INTERRUPT_ACKNOWLEDGEMENT')
    if frontier:summary['diagnostic_priorities'].append('EXAMINE_UNRESOLVED_BANKED_BRANCHES_WITH_MAPPER_AND_SOURCE_PROVENANCE')
    if trace.get('status') in ('UNTRANSLATED_INITIAL_CODE','BANKED_CODE_NOT_TRANSLATED'):
        summary['diagnostic_priorities'].insert(0,'RECOVER_SOURCE_ATTESTED_CODE_AT_OBSERVED_MAPPER_STATE')
    if not snapshots:summary['diagnostic_priorities'].append('COLLECT_NATIVE_CPU_CHECKPOINTS_FROM_NATIVE_PILOT')
    return summary
