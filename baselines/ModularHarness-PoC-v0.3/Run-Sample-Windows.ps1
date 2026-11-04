# Run the shipped synthetic sample through the installed v0.3 harness.
[CmdletBinding()]
param([string]$Output = '')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if([string]::IsNullOrWhiteSpace($Output)) { $Output = Join-Path $root 'build-win\reports\manual-sample' }
$bin = Join-Path $root 'build-win\bin\Release'
$exe = Join-Path $bin 'RecompDevHarness.exe'
$rom = Join-Path $root 'examples\recomp-pcode\synthetic.sms'
if(-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Build not present. Run .\Install-Windows.ps1 first.' }
& $exe --plugin-dir $bin --game rd_game_recomp_v0445 --case rom --rom $rom --validate --out $Output
if($LASTEXITCODE -ne 0) { throw 'Generated DLL sample failed.' }
Write-Host "Sample passed. Reports: $Output.*" -ForegroundColor Green
