$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$source=Join-Path $root 'host'
$build=Join-Path $root 'evidence\host-demo-v0420\build'
& cmake -S $source -B $build
if($LASTEXITCODE -ne 0){throw 'Host demo CMake configuration failed'}
& cmake --build $build --config Release --parallel 2
if($LASTEXITCODE -ne 0){throw 'Host demo C++ build failed'}
Write-Host "RecompDev synthetic host built under $build; NOT a converted game"
