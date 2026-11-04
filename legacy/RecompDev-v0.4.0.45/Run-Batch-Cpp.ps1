param(
  [string]$Database='',
  [string[]]$Source=@(),
  [string[]]$SourceRoot=@(),
  [string]$GoRoot='',
  [switch]$AttemptBounded,
  [string]$Output='',
  [int]$Timeout=120
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Database) { $Database=Join-Path $root 'catalogue.sqlite' }
if (-not $Output) { $Output=Join-Path $root 'evidence\batch-cpp-latest.json' }
if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) {throw "Missing database: $Database"}
$argsList=@((Join-Path $root 'recomp.py'),'--db',$Database,'batch-cpp','--output',$Output,'--timeout',([string]$Timeout))
foreach($path in $Source){ $argsList+=@('--source',$path) }
foreach($dir in $SourceRoot){ $argsList+=@('--source-root',$dir) }
if ($GoRoot) {$argsList+=@('--go-root',$GoRoot)}
if ($AttemptBounded) {$argsList+='--attempt-bounded'}
& py -3 @argsList
if ($LASTEXITCODE -ne 0){throw "Batch campaign failed; exit=$LASTEXITCODE"}
Write-Host "BATCH_REPORT=$Output"
Write-Host 'WHOLE_FUNCTION_PARITY=NOT_VERIFIED'
