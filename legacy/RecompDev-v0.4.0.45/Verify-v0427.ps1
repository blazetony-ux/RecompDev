$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0427.json
  if($LASTEXITCODE -ne 0){throw 'v0.4.0.27 release SHA-256 integrity failed'}
  & py -3 tools/Validate-v0427.py
  if($LASTEXITCODE -ne 0){throw 'v0.4.0.27 compiled/portable backend acceptance failed'}
  $tests=Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){Write-Host "CORE TEST: $($test.Name)"; & py -3 -m unittest discover -s tests -p $test.Name -q; if($LASTEXITCODE -ne 0){throw "Test failed: $($test.Name)"}}
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.27 PASS: full local regression and synthetic compilation. Authentic parity and playable Shinobi NOT ESTABLISHED.'
} finally {Pop-Location}
