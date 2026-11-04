# Optional original verifier on TEMPORARY copy, never inside the preserved legacy tree.
[CmdletBinding()]
param([switch]$Full)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$legacy = Join-Path $root 'legacy\RecompDev-v0.4.0.45'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('RecompDev-Legacy-Verify-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -ErrorAction Stop | Out-Null
try {
    $sandbox = Join-Path $tempRoot 'RecompDev-v0.4.0.45'
    Copy-Item -LiteralPath $legacy -Destination $sandbox -Recurse -Force
    $argsList = @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $sandbox 'Verify-v0445.ps1'))
    if ($Full) { $argsList += '-Full' }
    & powershell @argsList
    if ($LASTEXITCODE -ne 0) { throw 'Original verifier failed in disposable sandbox.' }
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
