param(
 [Parameter(Mandatory=$true)][string]$Rom,
 [string]$Project = '',
 [string]$InputEvents = '',
 [ValidateSet('window','headless')][string]$Mode='window',
 [ValidateSet('speaker','null')][string]$Audio='null',
 [int]$Frames=1800,
 [int]$Steps=12000000,
 [int]$Timeout=420,
 [switch]$MovementTrace
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=(Get-Command python.exe -ErrorAction Stop).Source
$env:PYTHONDONTWRITEBYTECODE='1'
$arguments=@('-B','-m','runtime_host.launch','--rom',$Rom,'--mode',$Mode,'--audio',$Audio,'--frames',"$Frames",'--steps',"$Steps",'--timeout',"$Timeout")
if ($MovementTrace) {$arguments+='--movement-trace'}
if ($Project) {$arguments+=@('--project',$Project)}
if ($InputEvents) {$arguments+=@('--input-events',$InputEvents)}
Push-Location $root
try {& $python @arguments;exit $LASTEXITCODE} finally {Pop-Location}
