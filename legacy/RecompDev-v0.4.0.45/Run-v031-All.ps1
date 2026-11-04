param(
 [string[]]$SourceRoot=@(),
 [string[]]$Source=@(),
 [string]$GhidraExe='',
 [string]$Database='',
 [string]$Output='',
 [int]$Limit=50,
 [string]$Compiler='',
 [switch]$NoPypcodeCheck
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Database){$Database=Join-Path $root 'catalogue.sqlite'}
if(-not $Output){$Output=Join-Path $root 'evidence\autopilot-v031'}
if(-not $GhidraExe){
  $ghRoots=@($env:GHIDRA_HOME,$env:GHIDRA_INSTALL_DIR)
  $bases=@('C:\Tools','C:\Projects','C:\Program Files','C:\Program Files (x86)',(Join-Path $env:USERPROFILE 'Downloads'))
  foreach($base in $bases){
    if(Test-Path -LiteralPath $base -PathType Container){
      $dirs=Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
          Where-Object {$_.Name -match 'ghidra'} | Sort-Object Name -Descending
      foreach($d in $dirs){$ghRoots+= $d.FullName}
    }
  }
  foreach($dir in $ghRoots){
    if(-not $dir){continue}
    $candidate=Join-Path $dir 'support\analyzeHeadless.bat'
    if(Test-Path -LiteralPath $candidate -PathType Leaf){$GhidraExe=$candidate;break}
  }
}
if(-not $GhidraExe -or -not (Test-Path -LiteralPath $GhidraExe -PathType Leaf)){
  throw 'Ghidra analyzeHeadless.bat not found. Supply -GhidraExe or set GHIDRA_HOME to your Ghidra installation.'
}
Write-Host "GHIDRA_EXE=$GhidraExe"
$argv=@((Join-Path $root 'recovery\autopilot.py'),'--db',$Database,'--ghidra-exe',$GhidraExe,'--output',$Output,'--limit',[string]$Limit)
foreach($x in $SourceRoot){$argv+=@('--source-root',$x)}
foreach($x in $Source){$argv+=@('--source',$x)}
if($Compiler){$argv+=@('--compiler',$Compiler)}
if($NoPypcodeCheck){$argv+='--no-pypcode-check'}
Push-Location $root
try {& py -3 @argv; if($LASTEXITCODE -ne 0){throw 'No targets successfully exported; inspect autopilot report.'}}
finally{Pop-Location}
