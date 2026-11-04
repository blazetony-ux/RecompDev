$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0412.json
  if($LASTEXITCODE -ne 0){throw 'Release source SHA-256 verification failed'}
  $tests=Get-ChildItem -LiteralPath (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){
    Write-Host "TEST SUITE: $($test.Name)"
    & py -3 -m unittest discover -s tests -p $test.Name -q
    if($LASTEXITCODE -ne 0){throw "RecompDev suite failed: $($test.Name)"}
  }
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.12 segmented regression suites PASSED'
} finally {Pop-Location}
