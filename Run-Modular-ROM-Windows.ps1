# v0.4.9.6 compatibility wrapper; resolve the separately deployed compiled controller.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Rom,
  [ValidateSet('discover','prepare','recover')][string]$Stage='prepare',
  [string]$Catalogue='', [string]$Output='', [string]$Ghidra='', [string]$Export='',
  [int]$Budget=150, [int]$Steps=200000, [int]$Frames=120,
  [int]$MaxRecoveries=2, [int]$MaxRounds=3, [int]$Timeout=720,
  [switch]$CaptureHardware
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
if (-not (Test-Path -LiteralPath $Rom -PathType Leaf)) { throw "ROM missing: $Rom" }
$argsList=@('--rom',$Rom,'--stage',$Stage,'--budget',[string]$Budget,'--steps',[string]$Steps,'--frames',[string]$Frames,'--max-recoveries',[string]$MaxRecoveries,'--max-rounds',[string]$MaxRounds,'--timeout',[string]$Timeout)
if($Catalogue){$argsList+=@('--catalogue',$Catalogue)}
if($Output){$argsList+=@('--out',$Output)}
if($Ghidra){$argsList+=@('--ghidra',$Ghidra)}
if($Export){$argsList+=@('--export',$Export)}
if($CaptureHardware){$argsList+='--capture-hardware'}
$compiled=Join-Path (Split-Path -Parent $root) 'RecompDev-Runtime\RecompDev.exe'
if(-not (Test-Path -LiteralPath $compiled -PathType Leaf)){throw "Compiled controller not installed: $compiled"}
& $compiled @argsList
if($LASTEXITCODE -ne 0) { throw "Modular workflow completed with a blocker/failure; inspect controller-report.json. Exit code: $LASTEXITCODE" }
