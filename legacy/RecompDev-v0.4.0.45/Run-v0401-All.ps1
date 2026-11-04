param(
 [string[]]$SourceRoot=@(),
 [string[]]$Source=@(),
 [int]$Budget=150,
 [int]$MaxFiles=300,
 [switch]$RunConversion,
 [int]$FunctionLimit=50,
 [string]$PreviousCampaign='',
 [string]$Database=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$working=if($Database){$Database}else{Join-Path $root 'catalogue.v0401-working.sqlite'}
$argv=@('-SourceRoot',$SourceRoot,'-Source',$Source,'-Budget',$Budget,'-MaxFiles',$MaxFiles)
if($Database){$argv+=@('-Database',$Database)}
if($PreviousCampaign){$argv+=@('-PreviousCampaign',$PreviousCampaign)}
& (Join-Path $root 'Run-v0401-Discover.ps1') @argv
if(-not $?){throw 'Discovery failed; native conversion was not started.'}
if($RunConversion){
  Write-Host 'NATIVE_CONVERSION=OPTIONAL_LEGACY_V0323_PIPELINE; WHOLE_FUNCTION_PARITY_NOT_CLAIMED'
  $conv=@('-Database',$working,'-Output',(Join-Path $root 'evidence\autopilot-v0401'),'-Limit',$FunctionLimit)
  foreach($item in $SourceRoot){$conv+=@('-SourceRoot',$item)}
  foreach($item in $Source){$conv+=@('-Source',$item)}
  & (Join-Path $root 'Run-v0323-All.ps1') @conv
  if(-not $?){throw 'Native conversion failed; discovery evidence remains saved.'}
}
Write-Host 'DISCOVERY_READY=YES; WORKBENCH=Run-Workbench.ps1'
