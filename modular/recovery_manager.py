"""Bounded, evidence-preserving continuation of original v0.4.0.45 native recovery.

This module NEVER infers code, rewrites legacy verified exports, promotes observations
as validated translations or mutates the owner catalogue. It only schedules separate
original recovery runs against one source-attested SQLite coverage cache.
"""
from __future__ import annotations
import json
import time
import sys
from pathlib import Path


def _number(value):
    return value if type(value) is int and value >= 0 else 0


def hardware_diagnostics(attempts, capture, last_session=None):
    if not capture:
        return {'capture_enabled': False, 'gameplay_parity': 'NOT_ESTABLISHED'}
    if not attempts:
        return {'capture_enabled': True, 'gameplay_parity': 'NOT_ESTABLISHED', 'observations': 'NO_ATTEMPTS'}
    last = attempts[-1]
    vdp = _number(last.get('vdp_writes'))
    psg = _number(last.get('psg_writes'))
    samples = _number(last.get('audio_nonzero_samples'))
    cram = _number(last.get('cram_nonzero_bytes'))
    interrupts = _number(last.get('maskable_interrupts'))
    frames = _number(last.get('frames'))
    hashes = _number(last.get('frame_hashes_count'))
    session = last_session or {}
    captured_hashes = session.get('frame_hashes') or []
    if not isinstance(captured_hashes,list): captured_hashes = []
    unique_hashes = len(set(str(h) for h in captured_hashes))
    flags = []
    if vdp and not cram: flags.append('VDP_ACTIVITY_WITH_NO_NONZERO_CRAM')
    if psg and not samples: flags.append('PSG_WRITES_WITHOUT_NONZERO_CAPTURED_AUDIO')
    if frames >= 10 and interrupts < 2: flags.append('LOW_MASKABLE_INTERRUPTS_FOR_FRAMES')
    if frames > 2 and captured_hashes and unique_hashes == 1: flags.append('ALL_CAPTURED_FRAME_HASHES_IDENTICAL')
    if _number(session.get('timing_unqualified_steps')): flags.append('UNQUALIFIED_TIMING_STEPS')
    return {
        'capture_enabled': True, 'gameplay_parity': 'NOT_ESTABLISHED',
        'vdp_writes': vdp, 'psg_writes': psg, 'audio_nonzero_samples': samples,
        'cram_nonzero_bytes': cram, 'maskable_interrupts': interrupts,
        'frames_observed': frames, 'frame_hashes_count': hashes,
        'video_activity': 'GUEST_VDP_WRITES_OBSERVED' if vdp else 'NO_GUEST_VDP_WRITES_OBSERVED',
        'palette_activity': 'NONZERO_CRAM_OBSERVED' if cram else 'NO_NONZERO_CRAM_OBSERVED',
        'audio_activity': 'NONZERO_CAPTURED_AUDIO' if samples else (
            'GUEST_PSG_WRITES_BUT_SILENT_CAPTURE' if psg else 'NO_CAPTURED_AUDIO_SIGNAL'),
        'interrupt_observation': 'LOW_MASKABLE_INTERRUPT_COUNT_REVIEW' if frames >= 10 and interrupts < 2 else 'OBSERVATION_ONLY',
        'frame_hashes_are_not_gameplay_parity': True,
        'unique_frame_hashes_observed': unique_hashes,
        'vblank_events': _number(session.get('vblank_events')),
        'cram_writes': _number(session.get('cram_writes')),
        'timing_unqualified_steps': _number(session.get('timing_unqualified_steps')),
        'review_flags': flags,
        'independent_hardware_reference_available': False,
        'interpretation': 'Raw counters only; verify VDP/CRAM, audio and IRQ timing against an independent reference.'
    }


def run_bounded(invoke, rec_args, recovery_dir, stage_dir, *, max_rounds=3,
                auto_continue=True, timeout=1200, capture=False):
    """Invoke original recovery per round, preserving each report and log.

    `invoke` is the approved legacy service adapter. `rec_args` must omit
    --output-dir; each round gets its own immutable output. Caller supplies a
    single persistent --coverage-cache path, backed by source-verified entries.
    """
    if not 1 <= max_rounds <= 12:
        raise ValueError('Invalid bounded recovery rounds (1..12)')
    if not 30 <= timeout <= 7200:
        raise ValueError('Invalid timeout')
    if '--output-dir' in [str(x) for x in rec_args]:
        raise ValueError('Output directory must be owned by recovery manager')
    if '--coverage-cache' not in [str(x) for x in rec_args]:
        raise ValueError('Recovery continuation requires a dedicated source-verified coverage cache')
    recovery_dir = Path(recovery_dir)
    stage_dir = Path(stage_dir)
    recovery_dir.mkdir(parents=True, exist_ok=False)
    stage_dir.mkdir(parents=True, exist_ok=False)
    rounds = []
    services = []
    all_attempts = []
    baseline_steps = 0
    baseline_frames = 0
    seen_last_stop = set()
    started = time.monotonic()
    last_session = None
    stop_reason = 'NO_RUN'
    stop_state = 'RECOVERY_BLOCKED'
    for index in range(max_rounds if auto_continue else 1):
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 1:
            stop_reason = 'CONTROLLER_TOTAL_TIMEOUT_EXHAUSTED'
            break
        out = recovery_dir / f'round-{index:02d}'
        log = stage_dir / f'round-{index:02d}'
        log.mkdir()
        args = list(rec_args) + ['--output-dir', out]
        service = invoke('legacy.recovery', args, log, timeout=max(1, int(remaining)))
        services.append(service)
        report_path = out / 'continuous-recovery-report.json'
        if not report_path.is_file():
            stop_reason = 'LEGACY_REPORT_MISSING'
            break
        doc = json.loads(report_path.read_text(encoding='utf8'))
        attempt_items = doc.get('attempts') or []
        if not isinstance(attempt_items, list):
            raise ValueError('Unrecognised legacy attempts report')
        round_attempts = [{**item, 'continuation_round': index} for item in attempt_items]
        if attempt_items and isinstance(attempt_items[-1].get('session_path'),str):
            sess = (out/attempt_items[-1]['session_path']).resolve()
            # Only inspect legacy-owned session artifacts within this round.
            if sess.is_relative_to(out.resolve()) and sess.is_file() and sess.stat().st_size < 8*1024*1024:
                last_session=json.loads(sess.read_text(encoding='utf8'))
        all_attempts.extend(round_attempts)
        new_entries = _number(doc.get('recovered_entries'))
        steps = _number(doc.get('maximum_steps_observed'))
        frames = _number(doc.get('maximum_frames_observed'))
        stop = attempt_items[-1] if attempt_items else {}
        key = (stop.get('status'), stop.get('physical_offset'), stop.get('pc'))
        summary = {
            'index': index, 'status': doc.get('status'), 'blocker': doc.get('blocker'),
            'service_return_code': service.get('return_code'),
            'legacy_compiled_successfully': bool(doc.get('compiled_successfully')), 
            'recovered_entries': new_entries, 'maximum_steps_observed': steps,
            'maximum_frames_observed': frames,
            'last_status': stop.get('status'), 'last_pc': stop.get('pc'),
            'last_physical_offset': stop.get('physical_offset'),
            'report': str(report_path),
            'source_verified_cache': doc.get('coverage_cache', {}).get('mode') == 'SOURCE_REATTESTED_SQLITE',
        }
        rounds.append(summary)
        print('RECOMPDEV_RECOVERY_PROGRESS '
              f'round={index+1}/{max_rounds if auto_continue else 1} '
              f'legacy_status={summary["status"]} blocker={summary["blocker"]} '
              f'native_steps={steps} frames={frames} '
              f'new_attested_entries={new_entries}', file=sys.stderr, flush=True)
        stop_state = doc.get('status') or 'RECOVERY_BLOCKED'
        stop_reason = doc.get('blocker') or stop_state
        if service.get('return_code') not in (0, 2):
            stop_reason = f'LEGACY_SERVICE_EXIT_{service.get("return_code")}'
            break
        if stop_state == 'CONTINUOUS_SESSION_COMPLETE':
            stop_reason = 'FRAME_BUDGET_REACHED'
            break
        if stop_state == 'STOPPED_WITHOUT_RECOVERABLE_CODE':
            stop_reason = 'EXECUTION_STEP_BUDGET_REACHED' if doc.get('blocker') == 'STEP_BUDGET_REACHED' else str(doc.get('blocker') or stop_state)
            break
        if stop_state != 'RECOVERY_BLOCKED' or doc.get('blocker') != 'RECOVERY_BUDGET_EXHAUSTED':
            break
        if not auto_continue:
            stop_reason = 'AUTO_CONTINUATION_DISABLED'
            break
        if not summary['source_verified_cache']:
            stop_reason = 'SOURCE_VERIFIED_CACHE_NOT_ACTIVE'
            break
        # No new attested instructions means another reset/replay cannot close the gap.
        if new_entries == 0:
            stop_reason = 'RECOVERY_NO_NEW_ATTESTED_CODE'
            break
        if key in seen_last_stop and steps <= baseline_steps and frames <= baseline_frames:
            stop_reason = 'RECOVERY_REPEATED_STOP_WITHOUT_EXECUTION_PROGRESS'
            break
        seen_last_stop.add(key)
        baseline_steps = max(baseline_steps, steps)
        baseline_frames = max(baseline_frames, frames)
        stop_reason = 'CONTINUATION_ROUND_LIMIT_REACHED'
    # These are historical attempt counts, NOT a count of unique instructions
    # executed or a claim that a game has advanced correctly.
    recovery_summary = {
        'schema': 'recompdev-bounded-native-recovery-v0.4.2',
        'status': 'CONTINUOUS_SESSION_COMPLETE' if stop_reason == 'FRAME_BUDGET_REACHED' else 'RECOVERY_LIMITED_OR_BLOCKED',
        'last_legacy_status': stop_state,
        'stop_reason': stop_reason, 'auto_continue': auto_continue,
        'max_rounds': max_rounds, 'rounds_completed': len(rounds),
        'compiled_successfully': any(x.get('legacy_compiled_successfully') or x.get('maximum_steps_observed', 0)>0 for x in rounds),
        'maximum_steps_observed': max((x['maximum_steps_observed'] for x in rounds),default=0),
        'maximum_frames_observed': max((x['maximum_frames_observed'] for x in rounds),default=0),
        'recovered_entries': sum(x['recovered_entries'] for x in rounds),
        'attempt_count': len(all_attempts), 'rounds': rounds,
        'attempts': all_attempts, 'hardware': hardware_diagnostics(all_attempts,capture,last_session),
        'gameplay': 'NOT_ESTABLISHED',
        'independent_reference_parity': 'NOT_TESTED',
        'native_gameplay_parity': 'NOT_ESTABLISHED',
        'source_coverage_qualification': 'SOURCE_BYTES_ONLY_NOT_SEMANTIC_PARITY',
        'note': 'Compiled native steps and frame counters are observations, not a correctness guarantee.',
        'elapsed_wall_seconds': round(time.monotonic()-started,3),
    }
    (recovery_dir / 'continuous-recovery-report.json').write_text(
        json.dumps(recovery_summary,indent=2,sort_keys=True)+'\n',encoding='utf8')
    return recovery_summary, services
