$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  $tests=Get-ChildItem -LiteralPath (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
  foreach($test in $tests){
    Write-Host "TEST SUITE: $($test.Name)"
    & py -3 -m unittest discover -s tests -p $test.Name -q
    if($LASTEXITCODE -ne 0){throw "RecompDev suite failed: $($test.Name)"}
  }
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'v0.4.0.9 segmented regression suites PASSED'
} finally {Pop-Location}
