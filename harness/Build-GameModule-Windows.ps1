param(
  [Parameter(Mandatory=$true)][string]$Rom,
  [Parameter(Mandatory=$true)][string]$Export,
  [string[]]$BankExports=@(),
  [int]$Steps=40,
  [ValidateRange(0,65535)][int]$Entry=0,
  [switch]$Validate
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  if(!(Test-Path -LiteralPath $Rom -PathType Leaf)){throw "ROM missing: $Rom"}
  if(!(Test-Path -LiteralPath $Export -PathType Leaf)){throw "P-code export missing: $Export"}
  $argsGen=@('tools/build_pcode_plugin.py','--rom',$Rom,'--export',$Export,
              '--out','generated/rd_game_recomp_v0445.cpp')
  foreach($bank in $BankExports){$argsGen+=@('--bank-export',$bank)}
  py -3 @argsGen
  if($LASTEXITCODE -ne 0){throw 'Source-attested P-code generation failed'}
  cmake -S . -B build-win -A x64
  if($LASTEXITCODE -ne 0){throw 'CMake configure failed'}
  cmake --build build-win --config Release --target rd_game_recomp_v0445 RecompDevHarness rd_machine_sms rd_cpu_z80 rd_discovery_jsonl rd_display_ppm rd_audio_wav rd_input_fixed
  if($LASTEXITCODE -ne 0){throw 'Game-module compilation failed'}
  $runArgs=@('--plugin-dir',(Join-Path $root 'build-win/bin/Release'),
    '--game','rd_game_recomp_v0445','--case','rom','--rom',$Rom,
    '--steps',"$Steps",'--entry',"$Entry",'--out',(Join-Path $root 'build-win/reports/owner-pcode'))
  if($Validate){$runArgs+='--validate'}
  & (Join-Path $root 'build-win/bin/Release/RecompDevHarness.exe') @runArgs
  if($LASTEXITCODE -ne 0){throw 'Hybrid execution failed (inspect stderr and evidence)'}
} finally {Pop-Location}
