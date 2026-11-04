#!/usr/bin/env python3
"""Explain a real source-verified recovery run's cost and progression.

Consumes continuous-recovery-report.json only.  No conjectural timings, ROM
access, gameplay assertions or CPU emulation. All figures come from recorded
per-attempt wall-clock durations and guest execution observations.
"""
import argparse,json,sys
from pathlib import Path

def summarize(report):
 if not isinstance(report,dict) or not isinstance(report.get('attempts'),list):
  raise ValueError('Missing structured recovery attempts')
 stages=('generation','build','reset_replays','source_recovery')
 totals={stage:0.0 for stage in stages}
 records=[]
 for row in report['attempts']:
  times=row.get('timings_seconds') or {}
  for stage in stages:
   value=times.get(stage,0)
   if not isinstance(value,(int,float)) or value<0 or value>1e7:
    raise ValueError('Invalid recovery timing value')
   totals[stage]+=value
  records.append({'attempt':row.get('index'),'frames':row.get('frames'),
      'translated_instructions':row.get('translated_instructions'),
      'new_source_attested_offsets':row.get('new_instruction_addresses',0),
      'status':row.get('status'),'timings_seconds':times})
 return {'schema':'recomp-recovery-performance-v0443',
         'source_sha256':report.get('source_sha256'),
         'attempt_count':len(records),'maximum_frames':report.get('maximum_frames_observed'),
         'cache':report.get('coverage_cache'),
         'timings_total_seconds':{k:round(v,3) for k,v in totals.items()},
         'attempts':records,'reference_parity':'NOT_TESTED',
         'gameplay':'NOT_ESTABLISHED'}

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--report',type=Path,required=True)
 p.add_argument('--output',type=Path)
 a=p.parse_args(argv)
 try:
  source=a.report.resolve(strict=True)
  if source.stat().st_size>8*1024*1024:raise ValueError('Recovery report too large')
  result=summarize(json.loads(source.read_text(encoding='utf-8')))
  output=a.output or source.with_name('recovery-performance-v0443.json')
  output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 except (ValueError,OSError,TypeError,KeyError) as e:p.error(str(e))
 print('PROFILE='+str(output),flush=True)
 print('ATTEMPTS='+str(result['attempt_count']),flush=True)
 print('MAXIMUM_FRAMES='+str(result['maximum_frames']),flush=True)
 print('CACHE_LOADED_OFFSETS='+str((result['cache'] or {}).get('loaded_instruction_offsets')),flush=True)
 return 0
if __name__=='__main__':sys.exit(main())
