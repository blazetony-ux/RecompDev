$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  Write-Host 'v0.4.0.36 [1/4] Verify immutable release manifest'
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0436.json
  if($LASTEXITCODE -ne 0){throw 'v0.4.0.36 release integrity gate failed'}
  Write-Host 'v0.4.0.36 [2/4] Mandatory inherited and new compiled acceptance'
  & py -3 tools/Validate-v0436.py
  if($LASTEXITCODE -ne 0){throw 'v0.4.0.36 compiled acceptance failed'}
  Write-Host 'v0.4.0.36 [3/4] Full repository Python regression suite'
  $tests=Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){Write-Host "CORE TEST: $($test.Name)"; & py -3 -m unittest discover -s tests -p $test.Name -q; if($LASTEXITCODE -ne 0){throw "Test failed: $($test.Name)"}}
  Write-Host 'v0.4.0.36 [4/4] Bridge regressions'
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.36 PASS: integrity, compiled acceptance, regressions and bridge tests.'
  Write-Host 'Shinobi MAME parity and seven authentic-game acceptance remain open until owner campaign evidence is returned.'
} finally {Pop-Location}
