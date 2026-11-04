param([Parameter(Mandatory=$true)][string]$InputFile,[string]$Database='',[string]$OutputDirectory='', [int]$MaxInstructions=100000,[switch]$SeedVectors)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath $InputFile -PathType Leaf)) {throw "Input does not exist: $InputFile"}
if (-not $Database) { $Database=Join-Path $root 'catalogue.sqlite' }
if (-not $OutputDirectory) { $OutputDirectory=Join-Path $root ('evidence\'+[IO.Path]::GetFileNameWithoutExtension($InputFile)) }
$scanArgs=@('--db',$Database,'scan','--input',$InputFile,'--out',$OutputDirectory,'--max-instructions',$MaxInstructions)
if ($SeedVectors) { $scanArgs += '--seed-vectors' }
& py -3 (Join-Path $root 'recomp.py') @scanArgs
if ($LASTEXITCODE -ne 0){throw 'Discovery failed; review previous error'}
