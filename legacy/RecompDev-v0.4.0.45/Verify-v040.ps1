$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try{
  & py -3 -m unittest discover -s tests -v
  if($LASTEXITCODE -ne 0){throw 'Catalogue/discovery/recovery tests failed'}
  & py -3 -m unittest discover -s bridge/tests -v
  if($LASTEXITCODE -ne 0){throw 'Cross-system bridge tests failed'}
  Write-Host 'V040_TESTS=PASS; WHOLE_GAME_DECOMPILATION=NOT_CLAIMED'
}finally{Pop-Location}
