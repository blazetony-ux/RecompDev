$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0424.json
  if($LASTEXITCODE -ne 0){throw 'Release source hash verification failed'}
  & py -3 tools/Validate-v0424.py
  if($LASTEXITCODE -ne 0){throw 'Integrated native acceptance gate failed'}
  $tests=Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){Write-Host "CORE TEST: $($test.Name)"; & py -3 -m unittest discover -s tests -p $test.Name -q; if($LASTEXITCODE -ne 0){throw "Test failed: $($test.Name)"}}
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.24 VERIFIED REGRESSIONS PASS. Authentic MAME parity, Windows interactive host and Shinobi gameplay still require separate qualification.'
} finally {Pop-Location}
