"""Assert semantic results, JSONL event counts, audio/video structure, and bank identity."""
import json,sys,wave
from pathlib import Path
p=Path(sys.argv[1]); main=json.loads((p/'main.report.json').read_text())
assert main['differential_pass'] and main['halted'] and main['native_steps']>=4 and main['fallback_steps']>=5,main
assert main['ram_c000']==42 and main['bank3']==2 and main['psg_writes']==1,main
assert main['cpu_a']==239,main # controller A with button A (bit 4) pressed, active-low
assert not main['runtime_rom_free'] and not main['full_z80_coverage']
assert len((p/'main.events.jsonl').read_text().splitlines())==main['discovery_events']
events=[json.loads(x) for x in (p/'main.events.jsonl').read_text().splitlines()]
assert sum(e['event']=='BANK_SWITCH' for e in events)==2,events
assert any(e['event']=='NATIVE_EXECUTED' and e['pc']==32768 and e['physical']==16384 for e in events),events
bank=json.loads((p/'bank2.report.json').read_text())
assert bank['differential_pass'] and bank['halted'] and bank['cpu_a']==153 and bank['native_steps']==1 and bank['fallback_steps']==1,bank
assert any(e['event']=='NATIVE_EXECUTED' and e['pc']==32768 and e['physical']==32768 for e in map(json.loads,(p/'bank2.events.jsonl').read_text().splitlines()))
other=json.loads((p/'input.report.json').read_text());assert other['cpu_a']==255 and other['differential_pass'],other
native=json.loads((p/'native_only.report.json').read_text());assert native['native_steps']==1 and native['fallback_steps']==0 and native['step_budget_exhausted']
ppm=(p/'main.ppm').read_bytes();assert ppm.startswith(b'P6\n256 192\n255\n') and len(ppm)>256*192*3
with wave.open(str(p/'main.wav'),'rb') as w:
 assert w.getframerate()==44100 and w.getnchannels()==1 and w.getnframes()==512
 frames=w.readframes(512);assert any(frames)
print('SEMANTIC_ASSET_AND_BANK_TESTS_PASS')

alternate=json.loads((p/'alternate.report.json').read_text())
assert alternate['differential_pass'] and alternate['halted'] and alternate['ram_c000']==42 and alternate['bank3']==2,alternate
assert alternate['cpu_a']==239 and alternate['native_steps']==4 and alternate['fallback_steps']==7
print('ALTERNATE_MACHINE_PLUGIN_TEST_PASS')
