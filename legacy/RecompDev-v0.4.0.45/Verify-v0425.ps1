$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0425.json
  if($LASTEXITCODE -ne 0){throw 'Release SHA-256 integrity failed'}
  & py -3 tools/Validate-v0425.py
  if($LASTEXITCODE -ne 0){throw 'Null backend compiled acceptance failed'}
  $tests=Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){Write-Host "CORE TEST: $($test.Name)"; & py -3 -m unittest discover -s tests -p $test.Name -q; if($LASTEXITCODE -ne 0){throw "Test failed: $($test.Name)"}}
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.25 PASS: null presentation plus complete legacy regressions. Authentic MAME parity and playable Shinobi NOT ESTABLISHED.'
} finally {Pop-Location}
