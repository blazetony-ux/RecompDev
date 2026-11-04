# RecompDev Modular Harness PoC v0.3: in-place build helper.
# For automatic installation with no extraction use Install-RecompDev-ModularHarness-v0.3.ps1.
[CmdletBinding()]
param([switch]$SkipBuild)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $root 'RELEASE_ID.txt') -PathType Leaf)) {
    throw 'Not a Modular Harness v0.3 source root.'
}
$id = (Get-Content -LiteralPath (Join-Path $root 'RELEASE_ID.txt') -Raw).Trim()
if ($id -ne 'RECOMPDEV_MODULAR_HARNESS_V0.3') {
    throw 'Release identifier mismatch; refusing mixed-version installation.'
}
if ($SkipBuild) {
    Write-Warning 'Build and tests skipped; nothing has been validated.'
    return
}
foreach ($tool in @('cmake','ctest','py')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing $tool: Visual Studio C++ Build Tools, CMake and Python 3 required."
    }
}
Push-Location $root
try {
    & cmake -S . -B build-win -A x64
    if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed.' }
    & cmake --build build-win --config Release --parallel
    if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
    & ctest --test-dir build-win -C Release --output-on-failure
    if ($LASTEXITCODE -ne 0) { throw 'At least one automated test failed.' }
    Write-Host 'Modular Harness v0.3 build and tests completed.' -ForegroundColor Green
} finally {
    Pop-Location
}
