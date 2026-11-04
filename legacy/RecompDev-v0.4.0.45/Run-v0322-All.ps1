param(
 [string[]]$SourceRoot=@(),
 [string[]]$Source=@(),
 [string]$GhidraExe='',
 [string]$Database='',
 [string]$Output='',
 [int]$Limit=50,
 [string]$Compiler='',
 [string]$PreviousExports='',
 [switch]$RefreshGhidra,
 [switch]$NoPypcodeCheck,
 [switch]$NoSampleCompare
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Output){$Output=Join-Path $root 'evidence\autopilot-v0322'}
if(-not $Database){
  # A NEW catalogue path. This is intentionally NOT catalogue.sqlite, which
  # can be held open by an existing Workbench on Windows (WinError 32).
  $Database=Join-Path $root 'catalogue.v0322-working.sqlite'
  $stamp=Join-Path $root '.v0322-working-catalogue.json'
  $previousDatabases=@(
    'C:\Projects\RecompDev-v0.3.2.1\catalogue.v0321-working.sqlite',
    'C:\Projects\RecompDev-v0.3.2\catalogue.sqlite',
    'C:\Projects\RecompDev-v0.3.1\catalogue.sqlite',
    (Join-Path $root 'catalogue.sqlite')
  )
  $copyArgs=@((Join-Path $root 'tools\import_previous_catalogue.py'),'--destination',$Database,'--stamp',$stamp)
  foreach($candidate in $previousDatabases){$copyArgs+=@('--source',$candidate)}
  & py -3 @copyArgs
  if($LASTEXITCODE -ne 0){throw 'Unable to prepare separate working catalogue. No existing database was overwritten.'}
}
if(-not (Test-Path -LiteralPath $Database -PathType Leaf)){throw "Catalogue not found: $Database"}
if(-not $PreviousExports -and -not $RefreshGhidra){
  foreach($candidate in @(
    'C:\Projects\RecompDev-v0.3.1\evidence\autopilot-v031\ghidra',
    'C:\Projects\RecompDev-v0.3.2\evidence\autopilot-v032\ghidra',
    (Join-Path $Output 'ghidra')
  )){
    if(Test-Path -LiteralPath $candidate -PathType Container){$PreviousExports=$candidate;break}
  }
}
if(-not $GhidraExe){
  $ghRoots=@($env:GHIDRA_HOME,$env:GHIDRA_INSTALL_DIR)
  foreach($base in @('C:\Tools','C:\Projects','C:\Program Files','C:\Program Files (x86)',(Join-Path $env:USERPROFILE 'Downloads'))){
    if(Test-Path -LiteralPath $base -PathType Container){
      $dirs=Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
          Where-Object {$_.Name -match 'ghidra'} | Sort-Object Name -Descending
      foreach($d in $dirs){$ghRoots+=$d.FullName}
    }
  }
  foreach($dir in $ghRoots){
    if(-not $dir){continue}
    $candidate=Join-Path $dir 'support\analyzeHeadless.bat'
    if(Test-Path -LiteralPath $candidate -PathType Leaf){$GhidraExe=$candidate;break}
  }
}
if($RefreshGhidra -and -not $GhidraExe){throw 'RefreshGhidra requires Ghidra analyzeHeadless.bat; supply -GhidraExe.'}
if(-not $GhidraExe -and -not $PreviousExports){throw 'Missing Ghidra exports AND Ghidra executable. Set -PreviousExports or -GhidraExe.'}
Write-Host "CATALOGUE=$Database"
Write-Host "SOURCE_ROOTS=$($SourceRoot.Count); EXPLICIT_SOURCES=$($Source.Count)"
Write-Host "GHIDRA_CACHE=$PreviousExports"
Write-Host "GHIDRA_EXE=$GhidraExe"
$argv=@((Join-Path $root 'recovery\autopilot.py'),'--db',$Database,'--output',$Output,'--limit',[string]$Limit)
foreach($x in $SourceRoot){$argv+=@('--source-root',$x)}
foreach($x in $Source){$argv+=@('--source',$x)}
if($GhidraExe){$argv+=@('--ghidra-exe',$GhidraExe)}
if($PreviousExports){$argv+=@('--previous-ghidra-dir',$PreviousExports)}
if($RefreshGhidra){$argv+='--refresh-ghidra'}
if($Compiler){$argv+=@('--compiler',$Compiler)}
if($NoPypcodeCheck){$argv+='--no-pypcode-check'}
if($NoSampleCompare){$argv+='--no-sample-compare'}
New-Item -Path $Output -ItemType Directory -Force | Out-Null
$report=Join-Path $Output 'autopilot-report.json'
# Never show an old report as evidence for a failed new invocation.
if(Test-Path -LiteralPath $report){Remove-Item -LiteralPath $report -Force}
Push-Location $root
try{
  & py -3 -u -X faulthandler @argv
  $exit=$LASTEXITCODE
  if($exit -ne 0){
    Write-Host "AUTOPILOT_EXIT_CODE=$exit"
    if(Test-Path -LiteralPath $report -PathType Leaf){
      try{
        $details=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        foreach($issue in @($details.issues)){
          if($null -eq $issue){continue}
          Write-Host "TARGET_ISSUE=$($issue.target_id); STATUS=$($issue.status); REASON=$($issue.reason)"
        }
        foreach($issue in @($details.source_scan_errors)){
          if($null -eq $issue){continue}
          Write-Host "SOURCE_SCAN_ISSUE=$($issue.source); ERROR=$($issue.error)"
        }
        Write-Host "DIAGNOSTIC_REPORT=$report"
      }catch{Write-Warning "Unable to parse diagnostic report: $_"}
    }else{
      Write-Warning "No final report written; Python may have terminated unexpectedly."
    }
    $stageFile=Join-Path $Output 'last-stage.json'
    if(Test-Path -LiteralPath $stageFile -PathType Leaf){
      Write-Host "LAST_STAGE_FILE=$stageFile"
      try {
        $stage=Get-Content -LiteralPath $stageFile -Raw | ConvertFrom-Json
        Write-Host "LAST_STAGE=$($stage.stage);TARGET=$($stage.target_id);ENTRY=$($stage.entry)"
      }catch{Write-Warning "Could not read stage checkpoint: $_"}
    }
    throw "Autopilot failed ($exit). See last-stage.json and autopilot-report.json (if present): $Output"
  }
}finally{Pop-Location}
