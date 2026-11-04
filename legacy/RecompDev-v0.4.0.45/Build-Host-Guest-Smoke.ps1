$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$compiler=Get-Command cl.exe -ErrorAction SilentlyContinue
if(-not $compiler){throw 'MSVC cl.exe unavailable; launch from Developer PowerShell for Visual Studio'}
$out=Join-Path $root 'host\recompdev-guest-synthetic.exe'
Push-Location (Join-Path $root 'host')
try {
  & $compiler.Source /nologo /EHsc /O2 /DRECOMPDEV_GUEST_BRIDGE StandaloneHost.cpp SyntheticGuest.cpp /Fe:$out user32.lib gdi32.lib winmm.lib
  if($LASTEXITCODE -ne 0){throw 'Guest host compile failed'}
  Write-Host "Synthetic guest/host test built: $out"
} finally {Pop-Location}
