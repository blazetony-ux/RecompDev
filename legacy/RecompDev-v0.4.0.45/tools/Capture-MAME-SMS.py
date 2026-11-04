"""Capture independent MAME Master System *frame-level* CPU observations.

Requires owner-installed MAME with Lua frame-notifier API and system media.
No emulator is downloaded/bundled; no implicit ROM access, shell, or parity claim.
MAME 0.289 API reference: https://docs.mamedev.org/luascript/
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nativecore.frame_oracle import sha256,validate_frames
from nativecore.bus_oracle import import_bus

def capture(mame,allowed_tool_root,rom,source_sha256,output_dir,system='sms',frames=120,timeout=180,rom_roots=()):
    mame=Path(mame).resolve();root=Path(allowed_tool_root).resolve()
    rom=Path(rom).resolve();output=Path(output_dir).resolve()
    if system not in ('sms','smspal','sms1','sms1pal'):
        raise ValueError('Unsupported MAME system ID (choose explicit SMS variant)')
    if type(frames) is not int or not 1<=frames<=1200 or type(timeout) is not int or not 1<=timeout<=600:
        raise ValueError('Invalid bounded capture limits')
    if not mame.is_file() or mame.is_symlink() or not mame.is_relative_to(root):
        raise ValueError('MAME executable must exist in the approved tool root')
    if not rom.is_file() or rom.is_symlink() or sha256(rom)!=source_sha256:
        raise ValueError('ROM missing or SHA-256 mismatch')
    if output.exists():raise ValueError('Output exists: immutable capture required')
    output.mkdir(parents=True)
    raw=output/'mame-frames.jsonl'
    bus=output/'mame-bus.jsonl'
    script=output/'mame-frame-capture.lua'
    template=Path(__file__).resolve().parents[1]/'examples/oracles/mame-sms-frame-capture.lua'
    shutil.copyfile(template,script)
    # MAME's default ROM/BIOS search is working-directory relative. Since we
    # isolate each capture under a separate evidence directory, provide a
    # fixed executable-local ROM path plus optional owner-selected directories.
    extra=[Path(p).resolve(strict=True) for p in rom_roots]
    roots=[mame.parent/'roms']+extra
    if any(not p.is_dir() for p in extra):
        raise ValueError('One or more MAME ROM/BIOS search directories are missing')
    import os
    argv=[str(mame),system,'-rompath',os.pathsep.join(str(p) for p in roots),
          '-cart',str(rom),'-autoboot_script',str(script),
          '-autoboot_delay','0','-nothrottle','-video','none','-sound','none','-skip_gameinfo']
    env=os.environ.copy();env['RECOMPDEV_MAME_FRAME_OUTPUT']=str(raw)
    env['RECOMPDEV_MAME_FRAME_LIMIT']=str(frames)
    env['RECOMPDEV_MAME_BUS_OUTPUT']=str(bus)
    with (output/'mame-stdout.log').open('wb') as out,(output/'mame-stderr.log').open('wb') as err:
        try:run=subprocess.run(argv,cwd=output,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                               timeout=timeout,check=False)
        except subprocess.TimeoutExpired as exc:
            (output/'capture-failed.txt').write_text('MAME timed out before the bounded frame capture ended.\n')
            raise ValueError('MAME frame capture timed out') from exc
    if run.returncode!=0:
        (output/'capture-failed.txt').write_text('MAME exited with nonzero code. See mame-stdout.log and mame-stderr.log.\n')
        raise ValueError('MAME returned nonzero exit code '+str(run.returncode))
    try:
        reference=validate_frames(raw,source_sha256,'MAME owner-installed '+system,frames)
    except ValueError:
        (output/'capture-failed.txt').write_text('Frame evidence incomplete or invalid. No parity claim.\n')
        raise
    bus_report=import_bus(bus,source_sha256,'MAME owner-installed '+system)
    (output/'selected-bus-reference.json').write_text(json.dumps(bus_report,indent=2)+'\n',encoding='utf-8')
    reference.update(selected_io_writes=bus_report['events'],selected_io_sha256=bus_report['raw_sha256'],
                     executable_sha256=sha256(mame),script_sha256=sha256(script),
                     system=system,requested_frames=frames)
    (output/'frame-observations.json').write_text(json.dumps(reference,indent=2)+'\n',encoding='utf-8')
    return {k:v for k,v in reference.items() if k!='observations'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('mame','allowed-tool-root','rom','source-sha256','output-dir'):p.add_argument('--'+flag,required=True)
    p.add_argument('--system',default='sms',choices=('sms','smspal','sms1','sms1pal'))
    p.add_argument('--frames',type=int,default=120);p.add_argument('--timeout',type=int,default=180)
    p.add_argument('--rom-root',action='append',default=[],help='Additional approved MAME BIOS/ROM directory; repeatable')
    a=p.parse_args()
    print(json.dumps(capture(a.mame,a.allowed_tool_root,a.rom,a.source_sha256,a.output_dir,a.system,a.frames,a.timeout,a.rom_root),indent=2))
if __name__=='__main__':main()
