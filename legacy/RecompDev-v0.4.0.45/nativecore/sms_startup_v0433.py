"""Guarded MAME/native selected-bus startup assessment, not CPU parity.

Uses independently obtained MAME bus writes and SHA-verified native event chunks.
A first-event difference has multiple possible causes (BIOS boot, reset state,
controller ports, CPU translation, and VDP timing). It is NOT attributed to an
instruction without aligned initial-state evidence.
"""
from pathlib import Path
import json
import re
from nativecore.bus_oracle import compare_bus
from nativecore.frame_oracle import sha256

SHA=re.compile(r'[a-f0-9]{64}\Z')
def inspect(reference_dir,pilot_report):
    refdir=Path(reference_dir).resolve(strict=True)
    pilot=Path(pilot_report).resolve(strict=True)
    if not pilot.is_file() or pilot.stat().st_size>4*1024*1024:
        raise ValueError('Pilot report missing or oversized')
    meta=refdir/'selected-bus-reference.json';bus=refdir/'mame-bus.jsonl'
    if not meta.is_file() or not bus.is_file():raise ValueError('MAME reference evidence incomplete')
    if meta.stat().st_size>128*1024 or bus.stat().st_size>24*1024*1024:
        raise ValueError('Reference evidence oversized')
    reference=json.loads(meta.read_text(encoding='utf-8'))
    candidate=json.loads(pilot.read_text(encoding='utf-8'))
    source=candidate.get('source_id')
    if not isinstance(source,str) or not SHA.fullmatch(source):raise ValueError('Invalid candidate source SHA-256')
    if reference.get('source_sha256')!=source:raise ValueError('MAME and native sources do not agree')
    trace=candidate.get('trace') or candidate
    rel=trace.get('event_stream_directory')
    if not isinstance(rel,str) or not re.fullmatch(r'event-streams/attempt-\d{2}-budget-\d{1,7}',rel):
        raise ValueError('Untrusted native event-stream path')
    native_dir=(pilot.parent/rel).resolve(strict=True)
    if not native_dir.is_relative_to(pilot.parent.resolve()):raise ValueError('Event stream escaped job root')
    comparison=compare_bus(reference,bus,candidate,native_dir)
    diff=comparison.get('first_divergence')
    context={
        'source_sha256':source,'reference_selected_writes':comparison['reference_writes'],
        'native_selected_writes':comparison['native_writes'],
        'reference_raw_sha256':sha256(bus),
        'pilot_report_sha256':sha256(pilot),
        'matching_selected_io_prefix':comparison['matching_prefix_writes'],
        'selected_io_status':comparison['status'],
        'first_selected_io_difference':diff,
        'same_initial_machine_state_proven':False,
        'cpu_instruction_boundaries_aligned':False,
        'frame_phase_aligned':False,
        'reference_mame_boot_path':'NOT_ATTESTED',
        'candidate_start_profile':'DIRECT_CARTRIDGE_RESET_WITH_APPROXIMATE_SMS_HARDWARE',
        'diagnostic_priorities':[]
    }
    if comparison['status']=='SELECTED_IO_DIVERGED':
        context['diagnostic_priorities']=[
            'CAPTURE_AND_ATTEST_BIOS_OR_DIRECT_CARTRIDGE_BOOT_PATH',
            'CAPTURE_COMPARABLE_INITIAL_CPU_MEMORY_MAPPER_AND_INPUT_STATE',
            'COMPARE_FIRST_ALIGNED_IO_OR_INSTRUCTION_CHECKPOINT',
            'ONLY_THEN_CLASSIFY_CPU_OR_HARDWARE_DEFECT'
        ]
        state='FIRST_IO_DIFFERENCE_WITH_UNALIGNED_START'
    elif comparison['status']=='MATCHED_SELECTED_IO_PREFIX':
        state='SELECTED_IO_PREFIX_MATCHED_START_STILL_UNALIGNED'
        context['diagnostic_priorities']=['ALIGN_INITIAL_STATE_AND_INSTRUCTION_BOUNDARIES_BEFORE_PARITY_CLAIM']
    else:
        state='INCOMPLETE_COMPARABLE_REFERENCE'
        context['diagnostic_priorities']=['CAPTURE_LONGER_MATCHING_REFERENCE_WITH_BOOT_PROVENANCE']
    context.update(schema='recomp-mame-sms-startup-assessment-v0433',status=state,
                   native_qualified=False,autonomous_patch_applied=False,
                   correctness='NOT_ESTABLISHED',evidence_scope='SELECTED_PSG_AND_VDP_CONTROL_PORT_WRITES_ONLY')
    return context
