param(
  [string[]]$SourceRoot=@('C:\Roms'),
  [string]$Output=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Output){$Output=Join-Path $root 'evidence\rom-name-audit'}
$argv=@((Join-Path $root 'tools\Audit-RecompDev-ROMs-v1.4.py'),'--output-dir',$Output)
foreach($d in $SourceRoot){$argv+=@('--root',$d)}
& py -3 @argv
if($LASTEXITCODE -ne 0){throw "Library inventory failed; exit=$LASTEXITCODE"}
Write-Host "ROM_AUDIT=$Output"
Write-Host 'NOTE=READ_ONLY; DOES_NOT_REGISTER_EXECUTABLE_FUNCTIONS'
