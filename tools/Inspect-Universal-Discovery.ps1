# Audit a completed run without rerunning the original discovery service or mutating catalogues.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Rom, [Parameter(Mandatory=$true)][string]$Catalogue,
      [Parameter(Mandatory=$true)][string]$DiscoveryReport, [Parameter(Mandatory=$true)][string]$Output,
      [switch]$ExportCandidates)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=(Get-Command python.exe -ErrorAction Stop).Source
$argsList=@('-m','discovery_integration.cli','--source',$Rom,'--working-catalogue',$Catalogue,'--discovery-report',$DiscoveryReport,'--output',$Output)
if($ExportCandidates){$argsList+='--export-candidates'}
Push-Location $root
try { & $python @argsList; if($LASTEXITCODE -ne 0){throw "Discovery audit blocked: $LASTEXITCODE"} }
finally { Pop-Location }
