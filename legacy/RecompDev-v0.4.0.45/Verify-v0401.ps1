$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try{
  & py -3 -m unittest discover -s tests -v
  if($LASTEXITCODE -ne 0){throw 'Catalogue/Workbench/discovery tests failed'}
  & py -3 -m unittest discover -s bridge/tests -v
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  Write-Host 'V0401_TESTS=PASS; ASSET_AND_NATIVE_ENGINE=V040_CARRY_FORWARD'
}finally{Pop-Location}
