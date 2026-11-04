param(
 [string[]]$SourceRoot=@(),
 [string[]]$Source=@(),
 [string]$Database='',
 [string]$Output='',
 [int]$Budget=150,
 [int]$MaxFiles=300,
 [switch]$RetryFailed,
 [string]$PreviousCampaign=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Output){$Output=Join-Path $root 'evidence\discovery-v040'}
if(-not $Database){
  # Never replace or rename catalogue.sqlite, even if the Workbench holds it open.
  $Database=Join-Path $root 'catalogue.v040-working.sqlite'
  $stamp=Join-Path $root '.v040-working-catalogue.json'
  $copyArgs=@((Join-Path $root 'tools\import_previous_catalogue.py'),'--destination',$Database,'--stamp',$stamp)
  foreach($candidate in @(
      'C:\Projects\RecompDev-v0.3.2.3\catalogue.v0323-working.sqlite',
      'C:\Projects\RecompDev-v0.3.2.2\catalogue.v0322-working.sqlite',
      'C:\Projects\RecompDev-v0.3.2.1\catalogue.v0321-working.sqlite',
      'C:\Projects\RecompDev-v0.3.1\catalogue.sqlite',
      (Join-Path $root 'catalogue.sqlite')
  )){$copyArgs+=@('--source',$candidate)}
  & py -3 @copyArgs
  if($LASTEXITCODE -ne 0){throw 'Could not prepare isolated catalogue. Existing installations were not modified.'}
}
if(-not (Test-Path -LiteralPath $Database -PathType Leaf)){throw "Missing catalogue: $Database"}
if($Source.Count -eq 0 -and $SourceRoot.Count -eq 0){throw 'Supply -SourceRoot and/or -Source with game files.'}
$argv=@('-m','discovery.engine','--db',$Database,'--output',$Output,'--budget',[string]$Budget,'--max-files',[string]$MaxFiles)
foreach($item in $SourceRoot){$argv+=@('--source-root',$item)}
foreach($item in $Source){$argv+=@('--source',$item)}
if($RetryFailed){$argv+='--retry-failed'}
if(-not $PreviousCampaign){
  foreach($candidate in @(
    'C:\Projects\RecompDev-v0.3.2.3\evidence\autopilot-v0323\compiled\campaign.json',
    'C:\Projects\RecompDev-v0.3.2.2\evidence\autopilot-v0322\compiled\campaign.json'
  )){if(Test-Path -LiteralPath $candidate -PathType Leaf){$PreviousCampaign=$candidate;break}}
}
if($PreviousCampaign){$argv+=@('--campaign',$PreviousCampaign)}
Write-Host "DISCOVERY_DATABASE=$Database"
Write-Host "DISCOVERY_OUTPUT=$Output"
Push-Location $root
try{
  & py -3 -u -X faulthandler @argv
  if($LASTEXITCODE -ne 0){throw "Autonomous discovery failed ($LASTEXITCODE). Check output folder: $Output"}
}finally{Pop-Location}
