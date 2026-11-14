"""Rights-cleared synthetic opcode-loop export demonstration (not real-game parity).

Only this explicitly labelled demo uses a preserved fixture generator for its
source-attested synthetic project. Production `export build` consumes an already
generated project and does not import frozen legacy services.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def build_demo(output: Path, *, cmake: str='cmake') -> dict:
    source=Path(__file__).resolve().parents[1]
    previous=list(sys.path)
    try:
        sys.path.insert(0,str(source/'legacy/RecompDev-v0.4.0.45'))
        from nativepilot.generator import generate_project
    finally:
        sys.path[:]=previous
    from standalone_export.exporter import build
    with tempfile.TemporaryDirectory(prefix='recompdev-synth-demo-') as folder:
        work=Path(folder)
        # The fixture program is authored for RecompDev testing and contains
        # one independently source-attested Z80 JP self branch. No third-party
        # game content or user-uploaded ROM is embedded in the release.
        rom=bytes([0xc3,0x00,0x00])+bytes(65536-3)
        data=work/'authored-synthetic-source.sms';data.write_bytes(rom)
        doc=json.loads((source/'harness/examples/recomp-pcode/function-export.json').read_text(encoding='utf8'))
        doc['source_sha256']=hashlib.sha256(rom).hexdigest()
        doc['target_id']='recompdev-standalone-demo-source-v1'
        doc['analyzer']='recompdev-authored-synthetic-demonstration'
        doc['functions']=[{'entry':0,'name':'AUTHOR_LICENSED_LOOP','instructions':[
            {'address':0,'length':3,'fallthrough':0,'mnemonic':'JP',
             'bytes_sha256':hashlib.sha256(rom[:3]).hexdigest(),
             'pcode':[{'op':'BRANCH','inputs':[{'space':'ram','offset':0,'size':1}]}]}
        ]}]
        project=work/'native-project'
        generate_project(doc,data,project)
        result=build(project=project,data=data,output=output,rights_confirmed=True,cmake=cmake)
        result['demo_fixture']='recompdev-authored-jp-loop'
        return result
