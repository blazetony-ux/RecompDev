# Start standalone read-only catalogue viewer. No RecompDev.exe or C++ build required.
[CmdletBinding()]
param(
    [string]$Database = 'C:\Projects\RecompDev-Data\catalogue.sqlite',
    [int]$Port = 8765,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$source = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python.exe -ErrorAction Stop).Source
$argsForPython = @('-B','-m','workbench.server','--db',$Database,'--port',[string]$Port)
if (-not $NoBrowser) { $argsForPython += '--open-browser' }
Push-Location $source
try { & $python @argsForPython; if ($LASTEXITCODE -ne 0) { throw "Workbench returned exit code $LASTEXITCODE" } }
finally { Pop-Location }
