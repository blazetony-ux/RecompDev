$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$cc=Get-Command cl.exe -ErrorAction SilentlyContinue
if(-not $cc){throw 'MSVC cl.exe is required: launch from Developer PowerShell for Visual Studio'}
Push-Location (Join-Path $root 'host')
try {
 $out=Join-Path $root 'host\RecompDevUniversalHost.exe'
 & $cc.Source /nologo /std:c++17 /EHsc /O2 UniversalHost.cpp /Fe:$out user32.lib gdi32.lib winmm.lib
 if($LASTEXITCODE -ne 0){throw 'Universal host build failed'}
 Write-Host 'Synthetic universal host built. NOT an authentic native game.'
}finally{Pop-Location}
