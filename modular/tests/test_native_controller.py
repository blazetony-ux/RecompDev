"""End-to-end direct compiled controller -> original discovery Python service."""
import json,subprocess,sys,tempfile,shutil
from pathlib import Path
exe=Path(sys.argv[1]).resolve(strict=True)
root=Path(sys.argv[2]).resolve(strict=True)
version=subprocess.run([str(exe),'--version'],text=True,capture_output=True,timeout=20)
assert version.returncode==0 and '0.4.6' in version.stdout,version
registry=subprocess.run([str(exe),'--plugins'],text=True,capture_output=True,timeout=30)
assert registry.returncode==0 and 'legacy.discovery' in registry.stdout,registry.stderr
sample=root/'harness/examples/recomp-pcode/synthetic.sms'
db=root/'legacy/RecompDev-v0.4.0.45/catalogue.sqlite'
with tempfile.TemporaryDirectory(prefix='RecompDev v042 spaces ') as temp:
    folder=Path(temp)
    rom=folder/'source with spaces.sms'
    shutil.copyfile(sample,rom)
    out=folder/'some evidence output'
    cmd=[str(exe),'--rom',str(rom),'--stage','legacy-discover','--catalogue',str(db),
         '--out',str(out),'--budget','5','--timeout','120',
         '--max-rounds','2','--no-auto-continue']
    process=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    assert process.returncode==0,(process.stdout[-2000:],process.stderr[-2000:])
    report=json.loads(process.stdout)
    assert report['status']=='DISCOVERY_COMPLETE',report
    assert report['source_image_unchanged'] and not report['production_catalogue_mutated']
    assert (out/'controller-report.json').is_file()
print('PASS: direct compiled controller to original discovery, spaced paths, source unchanged')
