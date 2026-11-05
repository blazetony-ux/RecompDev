"""Correlate live input, controller I/O reads, VDP scroll and sprite SAT evidence.

This report never labels an SAT entry as the player; a controller mapping match
is not a gameplay-parity claim, and apparent sprite displacement may be camera
scroll, animation, enemy movement or a rendering defect.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

HEADERS={
 'movement-controller.csv':['guest_cycle','logical_buttons','controller_dc','controller_dd'],
 'movement-port-reads.csv':['guest_cycle','pc','port','value'],
 'movement-frames.csv':['render_seq','guest_frame','guest_cycle','scroll_h_reg8','scroll_v_reg9','reg0','reg1','sat_base','sat_entries'],
 'movement-sprites.csv':['render_seq','guest_cycle','sat_index','x_raw','y_raw','pattern','screen_x','screen_y'],
}
LIMITS={'movement-controller.csv':50000,'movement-port-reads.csv':250000,
        'movement-frames.csv':36000,'movement-sprites.csv':1500000}

def read_table(directory:Path,name:str):
    path=directory/name
    if not path.is_file():raise ValueError('Missing movement trace: '+name)
    with path.open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames != HEADERS[name]:raise ValueError('Unexpected movement trace schema: '+name)
        rows=[]
        for row in reader:
            if len(rows)>=LIMITS[name]:raise ValueError('Movement diagnostic limit exceeded: '+name)
            values={k:int(v) for k,v in row.items()}
            if any(v<0 for k,v in values.items() if k!='screen_x'):
                raise ValueError('Negative unsigned movement trace value in '+name)
            rows.append(values)
    return rows

def analyze(directory:Path) -> dict:
    directory=Path(directory)
    controller=read_table(directory,'movement-controller.csv')
    reads=read_table(directory,'movement-port-reads.csv')
    frames=read_table(directory,'movement-frames.csv')
    sprites=read_table(directory,'movement-sprites.csv')
    for name,rows in [('controller',controller),('port reads',reads),('frames',frames),('sprites',sprites)]:
        if any(a['guest_cycle']>b['guest_cycle'] for a,b in zip(rows,rows[1:])):
            raise ValueError('Out-of-order guest-cycle diagnostic: '+name)
    if any(i!=row['render_seq'] for i,row in enumerate(frames)):
        raise ValueError('Non-contiguous diagnostic frame sequence')
    mismatches=[];direction_segments=[]
    for c in controller:
        expected=0xff ^ (c['logical_buttons']&0x3f)
        if c['controller_dc']!=expected:
            mismatches.append({'cycle':c['guest_cycle'],'logical_buttons':c['logical_buttons'],
                               'expected_dc':expected,'observed_dc':c['controller_dc']})
    controller_index=0
    port_mismatches=[];dc_reads=0;dd_reads=0
    for r in reads:
        if r['port'] not in (220,221):raise ValueError('Unexpected SMS controller port in trace')
        while controller_index+1<len(controller) and controller[controller_index+1]['guest_cycle']<=r['guest_cycle']:
            controller_index+=1
        if r['port']==220:
            dc_reads+=1
            if controller:
                expected=0xff ^ (controller[controller_index]['logical_buttons']&0x3f)
                if r['value']!=expected:
                    if len(port_mismatches)<50:port_mismatches.append({'cycle':r['guest_cycle'],'pc':r['pc'],
                                        'expected':expected,'observed':r['value']})
        else:dd_reads+=1 # TH output levels can change DD readback; cannot infer from host buttons.
    for i,c in enumerate(controller):
        direction=c['logical_buttons']&0x0f
        if not direction:continue
        stop=controller[i+1]['guest_cycle'] if i+1<len(controller) else ((frames[-1]['guest_cycle']+1) if frames else (c['guest_cycle']+1))
        between=[f for f in frames if c['guest_cycle']<=f['guest_cycle']<stop]
        if between:
            direction_segments.append({'start_cycle':c['guest_cycle'],'end_cycle':stop,'direction_bits':direction,
                       'frames_observed':len(between),'scroll_h_start':between[0]['scroll_h_reg8'],
                       'scroll_h_end':between[-1]['scroll_h_reg8'],
                       'scroll_v_start':between[0]['scroll_v_reg9'],
                       'scroll_v_end':between[-1]['scroll_v_reg9']})
    sat_counts={}
    for s in sprites:sat_counts[s['render_seq']]=sat_counts.get(s['render_seq'],0)+1
    sat_errors=[f['render_seq'] for f in frames if sat_counts.get(f['render_seq'],0)!=f['sat_entries']]
    scroll_changed=sum(1 for a,b in zip(frames,frames[1:]) if
                       (a['scroll_h_reg8'],a['scroll_v_reg9'])!=(b['scroll_h_reg8'],b['scroll_v_reg9']))
    result={'schema':'recompdev-movement-correlation-v1','status':'TRACE_COLLECTED',
            'controller_transitions':len(controller),'guest_controller_reads_dc':dc_reads,
            'guest_controller_reads_dd':dd_reads,'frames_traced':len(frames),
            'raw_sprite_entries_traced':len(sprites),'scroll_register_change_frames':scroll_changed,
            'host_to_guest_controller_mismatches':mismatches[:50],
            'guest_dc_port_read_mismatches':port_mismatches,'sprite_table_count_mismatch_frames':sat_errors[:50],
            'direction_segments':direction_segments[:100],
            'sms_controller_dc_mapping':'active_low: up=bit0 down=bit1 left=bit2 right=bit3 A=bit4 B=bit5',
            'dd_port_note':'DD can reflect IO-control TH outputs; recorded but not compared to logical input.',
            'movement_assessment':'INCONCLUSIVE_PLAYER_IDENTITY_AND_WORLD_COORDINATES_UNKNOWN',
            'interpreting_scroll':'VDP R8/R9 are unsigned wrapped scroll register values, not absolute camera/player coordinates.',
            'trace_validity':('MAPPING_MISMATCH' if mismatches or port_mismatches or sat_errors else
                              'CONSISTENT_OBSERVED_MAPPING' if dc_reads and controller else
                              'INSUFFICIENT_CONTROLLER_READS')}
    if (directory/'state-memory-regions.csv').is_file():
        from state_observer.analyze import write_report as analyze_memory
        mem=analyze_memory(directory,controller,input_clock_domain='z80_tstates')
        result['state_memory_diagnostics']='state-memory-diagnostics.json'
        result['state_memory_regions']=len(mem['regions'])
        result['state_memory_status']=mem['status']
        result['state_memory_candidate_count']=len(mem['candidate_byte_offsets'])
    return result

def write_report(directory:Path):
    result=analyze(directory)
    (Path(directory)/'movement-diagnostics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('evidence_dir',type=Path)
    args=p.parse_args();print(json.dumps(write_report(args.evidence_dir),indent=2))
