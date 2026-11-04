param([string]$Database='', [int]$Port=8777, [string[]]$RomRoot=@('C:\Roms'))
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Database){
  $init=Join-Path $root 'tools\Init-Shared-Catalogue-v0440.py'
  & py -3 $init --root $root
  if($LASTEXITCODE -ne 0){throw 'Shared catalogue validation/one-time bootstrap failed'}
  if($env:RECOMPDEV_CATALOGUE){$Database=$env:RECOMPDEV_CATALOGUE}
  elseif($env:RECOMPDEV_DATA_DIR){$Database=Join-Path $env:RECOMPDEV_DATA_DIR 'catalogue.sqlite'}
  else{$Database=Join-Path (Join-Path (Split-Path -Parent $root) 'RecompDev-Data') 'catalogue.sqlite'}
}
if(-not (Test-Path -LiteralPath $Database -PathType Leaf)){throw "Missing shared catalogue: $Database"}
Write-Host "RecompDev Workbench: http://127.0.0.1:$Port/"
Write-Host "Discovery page: http://127.0.0.1:$Port/discovery"
Write-Host "Native page: http://127.0.0.1:$Port/native"
Write-Host "Native execution: http://127.0.0.1:$Port/execution"
Write-Host "Tool orchestration: http://127.0.0.1:$Port/tooling"
Write-Host "DATABASE=$Database; MODE=SHARED_PERSISTENT_CATALOGUE"
$args=@('-3',(Join-Path $root 'recomp.py'),'--db',$Database,'serve','--port',[string]$Port)
foreach($folder in $RomRoot){if(Test-Path -LiteralPath $folder -PathType Container){$args+=@('--rom-root',$folder)}else{Write-Warning "ROM folder missing: $folder"}}
& py @args
if($LASTEXITCODE -ne 0){throw "Workbench failed: $LASTEXITCODE"}
# Historical migration candidates intentionally discovered by the shared
# importer: RecompDev-v0.4.0.37 catalogue.v0437-working.sqlite,
# RecompDev-v0.4.0.38 catalogue.v0438-working.sqlite,
# RecompDev-v0.4.0.36 and older. They are NOT rewritten.
