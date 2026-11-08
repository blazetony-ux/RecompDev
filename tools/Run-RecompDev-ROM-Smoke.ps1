# RecompDev v0.4.9.22 second-ROM acceptance: independent, bounded real-ROM jobs.
# ROMs remain in place. No Shinobi history is imported. No production DLLs change.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Controller,
 [Parameter(Mandatory=$true)][string]$RomDirectory,
 [string]$EvidenceRoot='C:\Projects\RecompDev-Evidence',
 [int]$TargetFrames=120,
 [int]$MaxCycles=1,
 [int]$RoundsPerCycle=1,
 [int]$TimeoutSeconds=120,
 [int]$StepBudget=2500000,
 [switch]$IncludeShinobi
)
$ErrorActionPreference='Stop'
if(!(Test-Path -LiteralPath $Controller -PathType Leaf)){throw 'Controller executable not found'}
if(!(Test-Path -LiteralPath $RomDirectory -PathType Container)){throw 'ROM directory not found'}
if($MaxCycles -lt 1 -or $MaxCycles -gt 128 -or $RoundsPerCycle -lt 1 -or $RoundsPerCycle -gt 8 -or $TargetFrames -lt 1 -or $TargetFrames -gt 36000 -or $TimeoutSeconds -lt 30 -or $TimeoutSeconds -gt 7200 -or $StepBudget -lt 1 -or $StepBudget -gt 20000000){throw 'Invalid bounded smoke parameters'}
$target=Join-Path $EvidenceRoot ('v0.4.9.22\smoke-tests\'+(Get-Date -Format 'yyyyMMddTHHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $target -Force | Out-Null
$roms=@(Get-ChildItem -LiteralPath $RomDirectory -Filter '*.sms' -File | Sort-Object Name | Where-Object {$IncludeShinobi -or $_.Name -notmatch '^Shinobi '})
if($roms.Count -eq 0){throw 'No .sms files selected'}
$all=New-Object System.Collections.Generic.List[object]
$index=0
foreach($rom in $roms){
 $index++
 $log=Join-Path $target ('rom-{0:D2}.log' -f $index)
 Write-Host ('RECOMPDEV_ROM_SMOKE_START='+$rom.Name)
 $ErrorActionPreference='Continue' # Native stderr is diagnostic, not a PowerShell stop condition.
 $output=@(& $Controller run --rom $rom.FullName --max-cycles $MaxCycles --rounds-per-cycle $RoundsPerCycle --target-frames $TargetFrames --timeout $TimeoutSeconds --step-budget $StepBudget --logging info 2>&1 | Tee-Object -FilePath $log)
 $code=$LASTEXITCODE
 $ErrorActionPreference='Stop'
 # For bounded jobs, 2 is a reported terminal recovery limit, not necessarily failure.
 $fields=@{}
 foreach($line in $output){$text=[string]$line;if($text -match '^(RECOMPDEV_[A-Z_]+)=(.+)$'){$fields[$Matches[1]]=$Matches[2]}}
 $all.Add([pscustomobject]@{Rom=$rom.Name;RomSha256=(Get-FileHash -LiteralPath $rom.FullName -Algorithm SHA256).Hash.ToLowerInvariant();ExitCode=$code;JobId=$fields['RECOMPDEV_JOB_ID'];Status=$fields['RECOMPDEV_JOB_STATUS'];Frames=$fields['RECOMPDEV_BEST_FRAMES'];Diagnostics=$fields['RECOMPDEV_DIAGNOSTICS_ZIP'];Log=$log})
 Write-Host ('RECOMPDEV_ROM_SMOKE_END='+$rom.Name+' EXIT='+$code+' FRAMES='+$fields['RECOMPDEV_BEST_FRAMES'])
}
$csv=Join-Path $target 'smoke-summary.csv'
$all | Export-Csv -LiteralPath $csv -NoTypeInformation -Encoding UTF8
Write-Host ('RECOMPDEV_ROM_SMOKE_REPORT='+$csv)
Write-Host ('RECOMPDEV_ROM_SMOKE_COUNT='+$all.Count)
$all | Format-Table -AutoSize
