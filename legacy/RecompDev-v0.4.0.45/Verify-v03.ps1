param([switch]$TestsOnly)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  & py -3 -m unittest discover -s tests -v
  if ($LASTEXITCODE -ne 0) {throw 'Catalogue tests failed'}
  & py -3 -m unittest discover -s bridge/tests -v
  if ($LASTEXITCODE -ne 0) {throw 'Cross-system bridge tests failed'}
  & py -3 (Join-Path $root 'recomp.py') summary
  if ($LASTEXITCODE -ne 0) {throw 'Catalogue summary failed'}
  Write-Host 'V03_TESTS=PASS;SOURCE_DATA=NOT_MODIFIED;PARITY=NOT_VERIFIED'
} finally {Pop-Location}
