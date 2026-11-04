param([string]$Configuration='Release')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  cmake -S . -B build-win -A x64
  if($LASTEXITCODE -ne 0){throw 'CMake configure failed'}
  cmake --build build-win --config $Configuration --parallel
  if($LASTEXITCODE -ne 0){throw 'Compilation failed'}
  ctest --test-dir build-win -C $Configuration --output-on-failure
  if($LASTEXITCODE -ne 0){throw 'Tests failed'}
  Write-Host "PoC binaries: $root\build-win\bin\$Configuration"
} finally {Pop-Location}
