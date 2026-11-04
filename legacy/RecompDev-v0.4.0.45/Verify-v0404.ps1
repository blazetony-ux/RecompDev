$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  & py -3 -m unittest discover -s tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'RecompDev v0.4.0.4 tests failed'}
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'RecompDev bridge tests failed'}
  Write-Host 'v0.4.0.4 test suites PASSED'
} finally {Pop-Location}
