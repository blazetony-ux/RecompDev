"""Black-box acceptance: compiled RecompDev -> native discovery DLLs, no Python subprocess."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

exe = Path(sys.argv[1]).resolve(strict=True)
plugindir = Path(sys.argv[2]).resolve(strict=True)

def sms():
    image = bytearray(0x8000)
    # reset: JP 0005, 0005: LD A,1, conditional JR +2, NOP, HALT
    image[:12] = bytes.fromhex('c305003e01200200767600') + bytes(1)
    image[0x7ff0:0x7ff8] = b'TMR SEGA'
    return bytes(image)

def md():
    data = bytearray(0x10000)
    data[0:4]=(0xff0000).to_bytes(4,'big')
    data[4:8]=(0x200).to_bytes(4,'big')
    data[0x100:0x104]=b'SEGA'
    return bytes(data)

def exefile():
    e=bytearray(0x1000)
    e[:8]=b'PS-X EXE'
    e[0x10:0x14]=(0x80010000).to_bytes(4,'little')
    e[0x18:0x1c]=(0x80010000).to_bytes(4,'little')
    e[0x1c:0x20]=(0x800).to_bytes(4,'little')
    return bytes(e)

def iso(raw=False):
    sectors=40
    data=bytearray(sectors*2048)
    pvd=16*2048
    data[pvd]=1;data[pvd+1:pvd+6]=b'CD001';data[pvd+6]=1
    root=pvd+156
    data[root]=34;data[root+2:root+6]=(20).to_bytes(4,'little')
    data[root+10:root+14]=(2048).to_bytes(4,'little')
    data[root+25]=2;data[root+32]=1;data[root+33]=0
    filename=b'SCENE.EXE;1'
    at=20*2048
    data[at]=33+len(filename);data[at+2:at+6]=(21).to_bytes(4,'little')
    data[at+10:at+14]=(0x1000).to_bytes(4,'little')
    data[at+32]=len(filename);data[at+33:at+33+len(filename)]=filename
    data[21*2048:23*2048]=exefile()
    if not raw:return bytes(data)
    disc=bytearray(sectors*2352)
    for n in range(sectors):
        disc[n*2352]=0
        disc[n*2352+1:n*2352+11]=b'\xff'*10
        disc[n*2352+11:n*2352+15]=bytes([0,0,0,2])
        disc[n*2352+15]=2
        disc[n*2352+24:n*2352+24+2048]=data[n*2048:(n+1)*2048]
    return bytes(disc)

def run(path,output,plugin_dir=plugindir,positive=True):
    cmd=[str(exe),'--stage','discover','--rom',str(path),'--plugin-dir',str(plugin_dir),'--out',str(output),'--budget','300']
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=40)
    if positive:
        assert p.returncode==0,(cmd,p.stdout,p.stderr)
        return json.loads((output/'native-discovery.json').read_text())
    assert p.returncode!=0,(cmd,p.stdout,p.stderr)
    if not output.exists(): pass
    else: assert any('EVIDENCE_EXISTS_REFUSING_OVERWRITE' in line for line in p.stderr.splitlines()), 'Unexpected evidence on failed qualification'
    return p.stderr

with tempfile.TemporaryDirectory(prefix='RecompDev native 0497 spaced ') as temp:
    root=Path(temp)
    samples=[('z80 cartridge.sms',sms(),'sms','z80'),('68000 cartridge.md',md(),'megadrive','m68000'),('psx main.exe',exefile(),'ps1','mips-r3000a'),('psx iso.iso',iso(),'ps1','mips-r3000a'),('raw sectors.img',iso(True),'ps1','mips-r3000a')]
    for index,(name,data,platform,cpu) in enumerate(samples):
        path=root/name;path.write_bytes(data)
        out=root/f'evidence {index}'
        result=run(path,out)
        assert result['platform']==platform,(name,result)
        assert result['cpu']==cpu,(name,result)
        assert result['source_sha256']==hashlib.sha256(data).hexdigest()
        assert result['source_fully_attested'] is True
        assert result['python_spawned'] is False
        assert not result['translation_attempted']
        assert len(result['plugins'])>=3
        assert all(len(row['sha256'])==64 for row in result['plugins'])
        assert path.read_bytes()==data
        if platform=='sms':
            assert result['source_length_verified_candidates']>=3,result
            assert result['control_flow_edges']>=2
            assert result['unresolved']>=0
            # Repeat in separate evidence: immutable source+instruction hashes.
            repeat=run(path,root/'repeat')
            assert result['blocks']==repeat['blocks']
            assert 'EVIDENCE_EXISTS_REFUSING_OVERWRITE' in run(path,out,positive=False)
            corrupted=bytearray(data);corrupted[0]=0xdd
            bad=root/'changed.sms';bad.write_bytes(corrupted)
            revised=run(bad,root/'revised')
            assert revised['source_sha256']!=result['source_sha256']
            assert revised['source_length_verified_candidates']<result['source_length_verified_candidates']
        if name=='raw sectors.img':
            assert result['sector_size']==2352,result
            assert result['executable_size']==0x1000
    # Deployed runtime layout: EXE in runtime root, locked DLLs in active/.
    installed=root/'runtime-like';installed.mkdir()
    shutil.copy2(exe,installed/exe.name)
    installed_plugins=installed/'active';installed_plugins.mkdir()
    for dll in plugindir.iterdir():
        if dll.name.startswith(('rd_format_','rd_cpu_z80','rd_machine_sms')):
            shutil.copy2(dll,installed_plugins/dll.name)
    installed_command=[str(installed/exe.name),'--stage','discover','--rom',str(root/samples[0][0]),
                       '--out',str(root/'installed-layout'), '--budget','300']
    installed_run=subprocess.run(installed_command, text=True,capture_output=True,timeout=40)
    assert installed_run.returncode==0,(installed_command,installed_run.stdout,installed_run.stderr)
    installed_report=json.loads((root/'installed-layout'/'native-discovery.json').read_text())
    assert installed_report['platform']=='sms'
    assert installed_report['python_spawned'] is False
    # Reject wrong kind without accidentally calling another plugin's inspect()
    badplugins=root/'bad plugins';badplugins.mkdir()
    for dll in plugindir.iterdir():
        if dll.name.startswith(('rd_format_','rd_cpu_z80','rd_machine_sms')):
            shutil.copy2(dll,badplugins/dll.name)
    first=next(badplugins.glob('rd_format_sms.*'))
    shutil.copy2(next(plugindir.glob('rd_cpu_z80.*')),first)
    rom=root/samples[0][0]
    assert 'PLUGIN_ABI_OR_KIND_REJECTED' in run(rom,root/'wrongkind',badplugins,positive=False)
    malformed=root/'garbage.iso';malformed.write_bytes(b'NOT A DISC')
    assert 'UNRECOGNISED_FORMAT' in run(malformed,root/'garbage-report',positive=False)
print('PASS: native discovery ABI, three CPU families, ISO2048/raw2352, deterministic source bytes, wrong-kind rejection')
