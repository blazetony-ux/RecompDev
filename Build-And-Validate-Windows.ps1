# RecompDev Modular Migration v0.4.3: builds a separate harness; no production migration.
[CmdletBinding()]
param([switch]$RunLegacyFull)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (((Get-Content -LiteralPath (Join-Path $root 'RELEASE_ID.txt') -Raw).Trim()) -ne 'RECOMPDEV_MODULAR_MIGRATION_V0.4.3') {
    throw 'Release identity mismatch. Refusing to build mixed sources.'
}
foreach ($tool in @('cmake', 'ctest', 'py')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing prerequisite: $tool (Visual Studio C++ Build Tools, CMake, Python required)."
    }
}
Push-Location $root
try {
    Write-Host 'G0: checking every original source file and preserved catalogue' -ForegroundColor Cyan
    & py -3 'migration/controller.py' verify
    if ($LASTEXITCODE -ne 0) { throw 'Source preservation gate failed.' }
    Write-Host 'Building compiled RecompDev controller plus the DLL harness against v0.4.0.45 sources' -ForegroundColor Cyan
    & cmake -S (Join-Path $root 'harness') -B (Join-Path $root 'build-win') -A x64
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
    & cmake --build (Join-Path $root 'build-win') --config Release --parallel
    if ($LASTEXITCODE -ne 0) { throw 'C++ harness build failed.' }
    & ctest --test-dir (Join-Path $root 'build-win') -C Release --output-on-failure
    if ($LASTEXITCODE -ne 0) { throw 'Regression gate failed; original tree untouched.' }
    if ($RunLegacyFull) {
        # Full legacy verifier may invoke external compiler/tool dependencies.
        # It runs from a disposable copy so the frozen original cannot be changed.
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Run-Legacy-Verify-Windows.ps1') -Full
        if ($LASTEXITCODE -ne 0) { throw 'Original v0.4.0.45 verifier failed.' }
    }
    & py -3 'migration/controller.py' verify
    if ($LASTEXITCODE -ne 0) { throw 'Post-build source integrity verification failed.' }
    Write-Host 'PASS: Modular Migration v0.4.3 built; preserved originals; original discovery and native workflow adapter gates passed.' -ForegroundColor Green
    $compiled = Join-Path $root 'build-win\bin\Release\RecompDev.exe'
    if (-not (Test-Path -LiteralPath $compiled -PathType Leaf)) { throw 'Compiled controller missing' }
    Copy-Item -LiteralPath $compiled -Destination (Join-Path $root 'RecompDev.exe') -Force
    Write-Host "Direct native controller: $root\RecompDev.exe"
    Write-Host "Harness: $root\build-win\bin\Release\RecompDevHarness.exe"
    Write-Warning 'Real owner-ROM execution, Ghidra availability, full original regressions, and gameplay parity still require separate validation.'
} finally {
    Pop-Location
}
