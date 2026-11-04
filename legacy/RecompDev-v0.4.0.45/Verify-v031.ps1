$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try{
  & py -3 -m unittest discover -s tests -v
  if($LASTEXITCODE -ne 0){throw 'Catalogue/function tests failed'}
  & py -3 -m unittest discover -s bridge/tests -v
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  & py -3 (Join-Path $root 'recomp.py') summary
  if($LASTEXITCODE -ne 0){throw 'Catalogue summary failed'}
  Write-Host 'V031_TESTS=PASS; ORIGINAL_CPU_PARITY=NOT_ESTABLISHED'
}finally{Pop-Location}
