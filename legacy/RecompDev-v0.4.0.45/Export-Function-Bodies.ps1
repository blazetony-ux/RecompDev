param(
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Target,
  [Parameter(Mandatory=$true)][string]$GhidraExe,
  [string]$Database='',
  [string]$Output=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Database){$Database=Join-Path $root 'catalogue.sqlite'}
if (-not $Output){$Output=Join-Path $root "evidence\ghidra\$Target.json"}
& py -3 (Join-Path $root 'recomp.py') --db $Database ghidra-headless --input $Source --target $Target --ghidra-exe $GhidraExe --output $Output
if($LASTEXITCODE -ne 0){throw "Ghidra export failed, exit=$LASTEXITCODE"}
Write-Host "GHIDRA_FUNCTION_EXPORT=$Output"
