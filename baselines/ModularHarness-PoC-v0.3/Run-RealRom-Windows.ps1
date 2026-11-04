# RecompDev Modular Harness v0.3: isolated, source-attested real-ROM probe / translation runner.
# No ROM bytes are included in release artifacts. The existing main RecompDev tree is untouched.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Rom,
  [string]$Export = '',
  [string[]]$BankExports = @(),
  [ValidateRange(1,100000)][int]$Steps = 40,
  [ValidateRange(0,65535)][int]$Entry = 0,
  [switch]$Validate
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$romPath = (Resolve-Path -LiteralPath $Rom -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $romPath -PathType Leaf)) { throw 'ROM file not found' }
if ([string]::IsNullOrWhiteSpace($Export) -and ($BankExports.Count -gt 0 -or $Validate)) {
  throw 'Bank exports and validation require a Ghidra P-code export.'
}
$bin = Join-Path $root 'build-win\bin\Release'
$exe = Join-Path $bin 'RecompDevHarness.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Install/build v0.3 first.' }
$sha = (Get-FileHash -LiteralPath $romPath -Algorithm SHA256).Hash.ToLowerInvariant()
$token = [Guid]::NewGuid().ToString('N').Substring(0,8)
$outDir = Join-Path $root ('build-win\reports\rom-' + $sha.Substring(0,12) + '-' + $token)
New-Item -Path $outDir -ItemType Directory -ErrorAction Stop | Out-Null
$prefix = Join-Path $outDir 'session'
Write-Host "ROM SHA256: $sha"
Write-Host "Isolated evidence: $outDir"
Push-Location $root
try {
  if ([string]::IsNullOrWhiteSpace($Export)) {
    if ($Validate) { throw 'Probe mode has no native reference parity to validate.' }
    $runArgs = @('--plugin-dir',$bin,'--case','rom','--rom',$romPath,
      '--game','rd_game_probe','--probe','--entry',"$Entry",'--steps',"$Steps",'--out',$prefix)
    Write-Host 'Running exploratory probe: unverified observations, no native translations.'
  } else {
    $expPath = (Resolve-Path -LiteralPath $Export -ErrorAction Stop).Path
    $g = @('tools/build_pcode_plugin.py','--rom',$romPath,'--export',$expPath,
        '--require-ghidra','--out','owner-generated/rd_game_owner.cpp')
    foreach ($path in $BankExports) {
      $bankPath = (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path
      $g += @('--bank-export',$bankPath)
    }
    & py -3 @g
    if ($LASTEXITCODE -ne 0) { throw 'ROM/P-code source verification or code generation failed.' }
    & cmake --build build-win --config Release --target rd_game_owner
    if ($LASTEXITCODE -ne 0) { throw 'Generated owner DLL did not compile.' }
    $runArgs = @('--plugin-dir',$bin,'--case','rom','--rom',$romPath,
      '--game','rd_game_owner','--entry',"$Entry",'--steps',"$Steps",'--out',$prefix)
    if ($Validate) { $runArgs += '--validate' }
    Write-Host 'Running verified-source compiled code with limited interpreter fallback.'
  }
  & $exe @runArgs
  $harnessCode = $LASTEXITCODE
  $events = "$prefix.events.jsonl"
  if ((Test-Path -LiteralPath $events -PathType Leaf) -and ((Get-Item -LiteralPath $events).Length -gt 0)) {
    $sidecar = Join-Path $outDir 'runtime-sidecar.sqlite'
    $a = @('tools/import_runtime_observations.py','--rom',$romPath,'--events',$events,'--output',$sidecar)
    $report = "$prefix.report.json"
    if (Test-Path -LiteralPath $report -PathType Leaf) { $a += @('--report',$report) }
    & py -3 @a
    if ($LASTEXITCODE -ne 0) { throw 'Runtime observation import failed; raw events have been retained.' }
    Write-Host "Unverified discovery sidecar created: $sidecar"
  } else { Write-Warning 'No execution events were recorded; no catalogue sidecar was created.' }
  if ($harnessCode -ne 0) {
    throw "Harness stopped (code $harnessCode). Limited Z80 coverage; see event log in $outDir. This is not gameplay parity."
  }
  Write-Host 'Session finished. This does NOT prove native gameplay or ROM independence.' -ForegroundColor Green
  Write-Host "Evidence: $outDir"
} finally { Pop-Location }
