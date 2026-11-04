# For users who already extracted the full source package. One-file installer is separately supplied.
[CmdletBinding()]
param([switch]$RunLegacyFull)
& (Join-Path $PSScriptRoot 'Build-And-Validate-Windows.ps1') -RunLegacyFull:$RunLegacyFull
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
