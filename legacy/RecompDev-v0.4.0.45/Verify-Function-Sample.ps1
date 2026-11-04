param(
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Manifest,
  [string]$Database='',
  [string]$Output=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Database){$Database=Join-Path $root 'catalogue.sqlite'}
$argsList=@((Join-Path $root 'recovery\verify.py'),'--db',$Database,'--source',$Source,'--manifest',$Manifest)
if($Output){$argsList+=@('--output',$Output)}
# Import path uses working directory so package modules resolve.
Push-Location $root
try {& py -3 @argsList; if($LASTEXITCODE -ne 0){Write-Warning "No sample parity established; exit=$LASTEXITCODE"}}finally{Pop-Location}
