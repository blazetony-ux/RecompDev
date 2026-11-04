"""Source-bound before/after campaign diagnostic; frame progress is NOT CPU or gameplay parity."""


def compare_campaign(baseline, current):
    if not isinstance(baseline, dict) or not isinstance(current, dict):
        raise ValueError('Invalid campaign documents')
    before = {g['slug']: g for g in baseline.get('games', []) if isinstance(g, dict) and isinstance(g.get('slug'), str)}
    after = {g['slug']: g for g in current.get('games', []) if isinstance(g, dict) and isinstance(g.get('slug'), str)}
    results=[]
    budgets_same=(baseline.get('frames_requested')==current.get('frames_requested') and
                  baseline.get('steps_requested')==current.get('steps_requested') and
                  baseline.get('max_recoveries')==current.get('max_recoveries') and
                  baseline.get('hardware_capture',True)==current.get('hardware_capture',True))
    for slug in sorted(set(before)|set(after)):
        b=before.get(slug,{});a=after.get(slug,{})
        result={'slug':slug,'source_sha256':a.get('sha256'),
                'status_before':b.get('status'),'status_after':a.get('status'),
                'frames_before':b.get('maximum_frames_observed'),'frames_after':a.get('maximum_frames_observed'),
                'recovered_before':b.get('recovered_instruction_addresses'),
                'recovered_after':a.get('recovered_instruction_addresses'),
                'blocker_before':b.get('blocker'),'blocker_after':a.get('blocker')}
        if not b or not a or a.get('status') in ('ROM_NOT_FOUND','ROM_READ_ERROR','AMBIGUOUS_SHINOBI_SOURCE'):
            result['assessment']='NO_PAIRED_RUN'
        elif not isinstance(b.get('sha256'),str) or b.get('sha256')!=a.get('sha256'):
            result['assessment']='SOURCE_IDENTITY_MISMATCH'
        elif not budgets_same:
            result['assessment']='BUDGETS_DIFFER_COMPARISON_UNQUALIFIED'
        elif type(b.get('maximum_frames_observed'))!=int or type(a.get('maximum_frames_observed'))!=int:
            result['assessment']='FRAME_EVIDENCE_MISSING'
        elif a['maximum_frames_observed']<b['maximum_frames_observed']:
            result['assessment']='FRAME_REGRESSION_OBSERVED'
        elif a['maximum_frames_observed']>b['maximum_frames_observed']:
            result['assessment']='FRAME_PROGRESS_NOT_PARITY'
        elif b.get('status')!=a.get('status') or b.get('blocker')!=a.get('blocker'):
            result['assessment']='SAME_FRAMES_DIFFERENT_BLOCKER'
        else:
            result['assessment']='NO_OBSERVED_FRAME_CHANGE'
        results.append(result)
    return {'schema':'recompdev-campaign-comparison-v0438','baseline_release':baseline.get('baseline_release'),
            'current_release':current.get('release'),'same_execution_budgets':budgets_same,
            'rom_identity_required':True,'cpu_parity':'NOT_TESTED','gameplay':'NOT_ESTABLISHED',
            'warning':'Frame progress alone is not reference parity or correct gameplay.', 'games':results}
