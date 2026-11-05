param(
  [Parameter(Mandatory=$true)][string]$Rom,
  [string]$EvidenceZip='',
  [int]$GuestHz=3579545,
  [int]$Frames=1800,
  [int]$Steps=15000000,
  [int]$MaxRecoveries=4,
  [int]$MaxRounds=8,
  [int]$Timeout=3600
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=(Get-Command python.exe -ErrorAction Stop).Source
$env:PYTHONDONTWRITEBYTECODE='1'
$args2=@('-B','-m','input_recovery.run','--rom',$Rom,
  '--guest-hz',"$GuestHz",'--frames',"$Frames",'--steps',"$Steps",
  '--max-recoveries',"$MaxRecoveries",'--max-rounds',"$MaxRounds",'--timeout',"$Timeout")
if ($EvidenceZip) {$args2+=@('--evidence-zip',$EvidenceZip)}
Push-Location $root
try {& $python @args2;exit $LASTEXITCODE} finally {Pop-Location}
