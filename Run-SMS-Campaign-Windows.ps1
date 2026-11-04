# Genuine RecompDev v0.4.0.45 7-game campaign, isolated under modular v0.4.1.
[CmdletBinding()]
param([string]$RomDir='C:\Roms\MASTERSYSTEM',[string]$Catalogue='',
      [string]$Output='',[int]$Frames=120,[int]$Steps=200000,
      [int]$MaxRecoveries=2,[int]$CompileTimeout=600,[int]$Timeout=3600,
      [switch]$CaptureHardware)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$argsList=@('-3',(Join-Path $PSScriptRoot 'modular\cli.py'),'run-campaign',
             '--rom-dir',$RomDir,'--frames',[string]$Frames,'--steps',[string]$Steps,
             '--max-recoveries',[string]$MaxRecoveries,
             '--compile-timeout',[string]$CompileTimeout,'--timeout',[string]$Timeout)
if($Catalogue){$argsList+=@('--catalogue',$Catalogue)}
if($Output){$argsList+=@('--out',$Output)}
if($CaptureHardware){$argsList+='--capture-hardware'}
& py @argsList
if($LASTEXITCODE -ne 0){throw "Seven-game campaign reported a blocker. Exit=$LASTEXITCODE"}
