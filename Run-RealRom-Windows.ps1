# Reuses validated v0.3 owner real-ROM entry point; no Shinobi hard-coding.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Rom,
 [string]$Export='',
 [string[]]$BankExports=@(),
 [ValidateRange(1,100000)][int]$Steps=40,
 [ValidateRange(0,65535)][int]$Entry=0,
 [switch]$Validate
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$runner=Join-Path $root 'harness\Run-RealRom-Windows.ps1'
# v0.3 original runner resolves its own build-win under harness/.
# This migration uses a separate shared build-win at the outer project root.
# Forward its parameter contract but correct the build path via a symlink-free wrapper.
$bin=Join-Path $root 'build-win\bin\Release'
$exe=Join-Path $bin 'RecompDevHarness.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Build the consolidation first.' }
$romPath=(Resolve-Path -LiteralPath $Rom -ErrorAction Stop).Path
$sha=(Get-FileHash -LiteralPath $romPath -Algorithm SHA256).Hash.ToLowerInvariant()
$outDir=Join-Path $root ('build-win\reports\rom-' + $sha.Substring(0,12) + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $outDir -ErrorAction Stop | Out-Null
$prefix=Join-Path $outDir 'session'
Push-Location (Join-Path $root 'harness')
try {
    if ([string]::IsNullOrWhiteSpace($Export)) {
        if ($Validate -or $BankExports.Count) { throw 'Validation/bank exports require authenticated base P-code export.' }
        $game='rd_game_probe'
    } else {
        $sourceExport=(Resolve-Path -LiteralPath $Export -ErrorAction Stop).Path
        $gen=@('tools/build_pcode_plugin.py','--rom',$romPath,'--export',$sourceExport,'--require-ghidra',
               '--out','owner-generated/rd_game_owner.cpp')
        foreach($bank in $BankExports) {
            $gen += @('--bank-export', (Resolve-Path -LiteralPath $bank -ErrorAction Stop).Path)
        }
        & py -3 @gen
        if ($LASTEXITCODE -ne 0) { throw 'Ghidra export rejected.' }
        & cmake --build (Join-Path $root 'build-win') --config Release --target rd_game_owner
        if ($LASTEXITCODE -ne 0) { throw 'Owner game DLL compilation failed.' }
        $game='rd_game_owner'
    }
    $runArgs=@('--plugin-dir',$bin,'--case','rom','--rom',$romPath,
             '--game',$game,'--entry',"$Entry",'--steps',"$Steps",'--out',$prefix)
    if ($game -eq 'rd_game_probe') { $runArgs += '--probe' }
    if ($Validate) { $runArgs += '--validate' }
    & $exe @runArgs
    $code=$LASTEXITCODE
    $events="$prefix.events.jsonl"
    if ((Test-Path -LiteralPath $events -PathType Leaf) -and ((Get-Item -LiteralPath $events).Length -gt 0)) {
        $sidecar=Join-Path $outDir 'runtime-sidecar.sqlite'
        $args=@('tools/import_runtime_observations.py','--rom',$romPath,'--events',$events,
                '--output',$sidecar)
        $report="$prefix.report.json"
        if (Test-Path -LiteralPath $report -PathType Leaf) { $args += @('--report',$report) }
        & py -3 @args
        if ($LASTEXITCODE -ne 0) { throw 'Evidence import failed; raw events preserved.' }
        Write-Host "Evidence sidecar: $sidecar"
    }
    Write-Host "Evidence directory: $outDir"
    if ($code -ne 0) { throw "Harness stopped with code $code; see logs for unsupported CPU paths." }
    Write-Warning 'UNVERIFIED exploratory probe: not real-game parity or ROM-free native execution.'
} finally { Pop-Location }
