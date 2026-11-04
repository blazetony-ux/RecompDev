# Command wrapper for isolated, independently versioned RecompDev components.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('paths','status','build','test','activate','rollback','accept','bump','full-build','full-test','deploy-all','release','apply-update')][string]$Action,
    [string]$Component,
    [string]$Argument
)
$ErrorActionPreference='Stop'
$source=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Get-Command python -ErrorAction SilentlyContinue
if ($python) { $exe=$python.Source; $prefix=@() }
else { $launcher=Get-Command py -ErrorAction SilentlyContinue; if (!$launcher) {throw 'Python 3 is required'}; $exe=$launcher.Source; $prefix=@('-3') }
$env:PYTHONDONTWRITEBYTECODE='1'
$argsList=@($prefix)+@((Join-Path $source 'workspace\manager.py'),$Action)
if ($Component) { $argsList+=@($Component) }
if ($Argument) { $argsList+=@($Argument) }
& $exe @argsList
if ($LASTEXITCODE -ne 0) {throw "Workspace action '$Action' failed (exit code $LASTEXITCODE)."}
