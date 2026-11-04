"""Direct compiled RecompDev.exe offline hardware review test."""
import json,subprocess,sys,tempfile,wave
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from modular.tests.test_hardware_review import make_fixture
exe=Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix="RecompDev offline review spaces ") as temp:
    base=Path(temp);make_fixture(base/'run',True)
    command=[str(exe),'--analyze-evidence',str(base/'run'),'--out',str(base/'review output')]
    p=subprocess.run(command,text=True,capture_output=True,timeout=60)
    assert p.returncode==0,(p.stdout,p.stderr)
    result=json.loads(p.stdout)
    assert result['status']=='HARDWARE_REVIEW_COMPLETE',result
    assert result['hardware_review']['asset_recovery']['status']=='RAW_VRAM_REQUIRED'
    assert (base/'review output-evidence.zip').is_file()
    assert 'RECOMPDEV_EVIDENCE_ZIP=' in p.stderr
print('PASS: compiled CLI runs offline image/audio/timing review, bundles evidence, no ROM')
