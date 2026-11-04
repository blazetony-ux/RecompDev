param(
  [string]$Database='',
  [string[]]$Source=@(),
  [string[]]$SourceRoot=@(),
  [string[]]$GhidraExport=@(),
  [string]$Output='',
  [int]$Limit=50,
  [string]$RizinJson='',
  [switch]$RequireDual,
  [switch]$PypcodeCheck,
  [switch]$NoCompile,
  [string]$Compiler=''
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Database){$Database=Join-Path $root 'catalogue.sqlite'}
if (-not $Output){$Output=Join-Path $root 'evidence\functions-v031'}
if ($GhidraExport.Count -eq 0){throw 'Provide Ghidra raw-P-code export(s), or run Export-Function-Bodies.ps1 first.'}
$argsList=@((Join-Path $root 'recomp.py'),'--db',$Database,'recover-cpp','--output',$Output,'--limit',[string]$Limit)
foreach($f in $Source){$argsList+=@('--source',$f)}
foreach($d in $SourceRoot){$argsList+=@('--source-root',$d)}
foreach($f in $GhidraExport){$argsList+=@('--ghidra-export',$f)}
if($RizinJson){$argsList+=@('--rizin-json',$RizinJson)}
if($RequireDual){$argsList+='--require-dual'}
if($PypcodeCheck){$argsList+='--pypcode-check'}
if($NoCompile){$argsList+='--no-compile'}
if($Compiler){$argsList+=@('--compiler',$Compiler)}
& py -3 @argsList
if ($LASTEXITCODE -ne 0){throw "Function recovery failed, exit=$LASTEXITCODE"}
Write-Host "FUNCTION_REPORT=$(Join-Path $Output 'campaign.json')"
Write-Host 'ORIGINAL_CPU_PARITY=NOT_ESTABLISHED'
