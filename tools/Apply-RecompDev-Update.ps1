# One-line incremental source update. Never runs a full reinstallation.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Package)
$ErrorActionPreference='Stop'
if (!(Test-Path -LiteralPath $Package)) {throw "Update package missing: $Package"}
& (Join-Path $PSScriptRoot 'RecompDev-Workspace.ps1') -Action apply-update -Component $Package
if ($LASTEXITCODE -ne 0) {throw 'Update failed.'}
