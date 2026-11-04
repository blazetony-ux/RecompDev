$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  Write-Host 'v0.4.0.38 [1/4] Verify immutable release manifest'
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0438.json
  if($LASTEXITCODE -ne 0){throw 'v0.4.0.38 release integrity failed'}
  Write-Host 'v0.4.0.38 [2/4] Compiled native output qualification + inherited acceptance'
  & py -3 tools/Validate-v0438.py
  if($LASTEXITCODE -ne 0){throw 'v0.4.0.38 compiled acceptance failed'}
  Write-Host 'v0.4.0.38 [3/4] Full repository Python regressions'
  $tests=Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){Write-Host "CORE TEST: $($test.Name)"; & py -3 -m unittest discover -s tests -p $test.Name -q; if($LASTEXITCODE -ne 0){throw "Test failed: $($test.Name)"}}
  Write-Host 'v0.4.0.38 [4/4] Bridge regressions'
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.38 PASS: integrity, compiled hardware output, regressions and bridge tests.'
  Write-Host 'Independent MAME/native alignment and commercial-game correctness remain UNPROVEN.'
} finally {Pop-Location}
