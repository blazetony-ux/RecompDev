# RecompDev permanent Git-managed source release installer (release protocol v1).
# PowerShell 5.1 compatible. This script is *infrastructure*, not the RecompDev runtime.
# First use: execute this file from Downloads; a promoted release installs the same
# file into the Git-controlled RecompDev root. Subsequent releases reuse that copy.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
    [ValidateSet('Validate','Install')][string]$Mode='Validate',
    [switch]$PublishOrigin,
    [string]$Source='C:\Projects\RecompDev'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$env:PYTHONDONTWRITEBYTECODE='1'
$Source=[IO.Path]::GetFullPath($Source).TrimEnd('\')
$Package=[IO.Path]::GetFullPath($Package)
$projectParent=Split-Path -Parent $Source
$archiveRoot=Join-Path $projectParent 'RecompDev-Archive'
$evidenceRoot=Join-Path $projectParent 'RecompDev-Evidence'
$buildRoot=Join-Path $projectParent 'RecompDev-Build'
$runtimeRoot=Join-Path $projectParent 'RecompDev-Runtime'
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+$PID
$job=Join-Path $buildRoot ('release-transactions\'+$stamp)
$payload=Join-Path $job 'payload'
$staged=Join-Path $projectParent ('RecompDev-ReleaseStage-'+$stamp)
$cmakeBuild=Join-Path $job 'cmake'
$baseZip=Join-Path $job 'git-head.zip'
$backup=Join-Path $archiveRoot ('release-backups\'+$stamp)
$logDir=Join-Path $evidenceRoot 'release-installer'
$transcript=Join-Path $logDir ('release-'+$stamp+'.log')
$git=$null; $python=$null; $cmake=$null; $ctest=$null
$release=''; $oldHead=''; $newHead=''; $madeCommit=$false; $madeTag=$false
$changedSource=$false; $runtimeTouched=$false; $tag=''; $releaseOk=$false
$runtimeSnapshot=@(); $sourceSnapshot=@(); $stateBackup=$null; $existingTag=$false
$manifest=$null

function Assert([bool]$Condition,[string]$Message){if(-not $Condition){throw $Message}}
function Run([string]$Executable,[string[]]$Arguments,[string]$Failure){
  & $Executable @Arguments
  if($LASTEXITCODE -ne 0){throw "$Failure (exit $LASTEXITCODE)"}
}
function Hash([string]$Path){
  Assert (Test-Path -LiteralPath $Path -PathType Leaf) "Missing file: $Path"
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function ValidPath([string]$Rel){
  # v1 releases use portable ASCII source paths. Never allow a ZIP to escape staging.
  # .md is valid Markdown source (README, CHANGELOG, component documentation);
  # do not confuse it with a Mega Drive ROM extension. Validate .md payloads as UTF-8 text below.
  if($Rel -notmatch '^[a-zA-Z0-9_./-]+$' -or $Rel.StartsWith('/') -or
      $Rel.Contains('//') -or $Rel -match '(^|/)(\.|\.\.)(/|$)' -or
      $Rel.StartsWith('legacy/') -or $Rel.StartsWith('baselines/') -or
      ($Rel -eq '.git') -or $Rel.StartsWith('.git/') -or $Rel -match '\.(exe|dll|so|dylib|rom|sms|iso|img|bin)$'){
    throw "Unsafe or protected package path: $Rel"
  }
}
function GitBlobToFile([string]$Rel,[string]$Target){
  # Git's canonical blob bytes, not Windows checkout CRLF or ZIP extraction bytes.
  $psi=New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName=$git
  $psi.Arguments='-C "'+$Source+'" cat-file blob "HEAD:'+$Rel+'"'
  $psi.UseShellExecute=$false
  $psi.RedirectStandardOutput=$true
  $psi.RedirectStandardError=$true
  $psi.CreateNoWindow=$true
  $proc=New-Object System.Diagnostics.Process
  $proc.StartInfo=$psi
  Assert $proc.Start() "Unable to execute Git for $Rel"
  $dir=Split-Path -Parent $Target
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
  try{
    $out=[IO.File]::Create($Target)
    try{$proc.StandardOutput.BaseStream.CopyTo($out)}finally{$out.Dispose()}
    $err=$proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    Assert ($proc.ExitCode -eq 0) "Failed reading committed Git blob $Rel : $err"
  }finally{$proc.Dispose()}
}
function RestoreManifestDeclaredHistoricalFiles {
  # A git archive contains tracked source only. The historical integrity
  # manifest also lists a small number of intentionally ignored evidence files.
  # A clean git status cannot prove those files are present or unchanged.
  # Restore ONLY missing or byte-mismatched manifest-declared frozen files,
  # only after checking their original length and SHA-256 against the signed-off
  # committed manifest. Never modify the source checkout or change the manifest.
  $inventoryPath=Join-Path $staged 'migration\source-integrity-manifest.json'
  Assert (Test-Path -LiteralPath $inventoryPath -PathType Leaf) 'Missing immutable history manifest in Git stage'
  $inventory=Get-Content -LiteralPath $inventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
  Assert ($null -ne $inventory.sources) 'Invalid historical integrity manifest'
  $groups=@(
    @{key='recompdev_0445';prefix='RecompDev-v0.4.0.45/';root='legacy/RecompDev-v0.4.0.45';count=581},
    @{key='harness_03';prefix='ModularHarness-PoC-v0.3/';root='baselines/ModularHarness-PoC-v0.3';count=61}
  )
  $restored=0
  foreach($group in $groups){
    $property=$inventory.sources.PSObject.Properties[$group.key]
    Assert ($null -ne $property) ('Missing historical inventory: '+$group.key)
    $spec=$property.Value
    Assert ([int]$spec.file_count -eq [int]$group.count) ('Historical inventory file count changed: '+$group.key)
    Assert (@($spec.entries).Count -eq [int]$group.count) ('Historical inventory entries missing: '+$group.key)
    foreach($entry in $spec.entries){
      $archiveRel=[string]$entry.path
      Assert ($archiveRel.StartsWith([string]$group.prefix,[StringComparison]::Ordinal)) ('Unexpected historical path: '+$archiveRel)
      $tail=$archiveRel.Substring(([string]$group.prefix).Length)
      Assert ($tail -match '^[a-zA-Z0-9_./-]+$' -and -not $tail.StartsWith('/') -and
              -not $tail.Contains('//') -and -not ($tail -match '(^|/)(\.|\.\.)(/|$)')) ('Unsafe historical path: '+$tail)
      $rel=([string]$group.root)+'/'+$tail
      $stageFile=Join-Path $staged ($rel.Replace('/','\'))
      # Git archive may omit ignored evidence or normalise tracked CRLF files.
      # The preservation manifest, not Git's storage format, owns the original
      # frozen byte identity. Canonicalise the stage from a verified source copy.
      $stageMatches=Test-Path -LiteralPath $stageFile -PathType Leaf
      if($stageMatches){
        $stageMatches=((Get-Item -LiteralPath $stageFile).Length -eq [long]$entry.bytes)
        if($stageMatches){$stageMatches=((Hash $stageFile) -eq [string]$entry.sha256)}
      }
      if(-not $stageMatches){
        $originalFile=Join-Path $Source ($rel.Replace('/','\'))
        Assert (Test-Path -LiteralPath $originalFile -PathType Leaf) ('Historical file absent in source checkout: '+$rel)
        Assert ([string]$entry.sha256 -match '^[a-f0-9]{64}$') ('Malformed historical file hash: '+$rel)
        Assert ((Get-Item -LiteralPath $originalFile).Length -eq [long]$entry.bytes) ('Historical source byte count mismatch: '+$rel)
        Assert ((Hash $originalFile) -eq [string]$entry.sha256) ('Historical source SHA-256 mismatch: '+$rel)
        New-Item -ItemType Directory -Path (Split-Path -Parent $stageFile) -Force | Out-Null
        Copy-Item -LiteralPath $originalFile -Destination $stageFile -Force
        Assert ((Hash $stageFile) -eq [string]$entry.sha256) ('Historical staged SHA-256 mismatch: '+$rel)
        $restored++
      }
    }
  }
  Write-Host "RECOMPDEV_STAGED_HISTORICAL_RESTORED=$restored"
}

function ExtractPackage([string]$ZipPath,[string]$Destination){
  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive=[IO.Compression.ZipFile]::OpenRead($ZipPath)
  try{
    Assert ($archive.Entries.Count -le 10000) 'Excessive ZIP member count'
    $seen=@{}; [long]$total=0
    foreach($entry in $archive.Entries){
      $rel=$entry.FullName
      Assert (-not [string]::IsNullOrWhiteSpace($entry.Name)) "Directory entries not permitted: $rel"
      Assert ($rel -eq 'release-manifest.json' -or $rel.StartsWith('files/')) "Unknown ZIP member: $rel"
      if($rel -ne 'release-manifest.json'){ValidPath $rel.Substring(6)}
      Assert (-not $seen.ContainsKey($rel)) "Duplicate ZIP member: $rel"
      $seen[$rel]=$true
      $total+=[long]$entry.Length
      Assert ($total -le 536870912) 'Expanded ZIP exceeds 512 MiB limit'
      $path=Join-Path $Destination ($rel.Replace('/','\'))
      New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
      $inputStream=$entry.Open()
      try{
        $outputStream=[IO.File]::Create($path)
        try{$inputStream.CopyTo($outputStream)}finally{$outputStream.Dispose()}
      }finally{$inputStream.Dispose()}
      Assert ((Get-Item -LiteralPath $path).Length -eq $entry.Length) "ZIP length mismatch: $rel"
    }
    Assert ($seen.ContainsKey('release-manifest.json')) 'Missing release-manifest.json'
    return $seen
  }finally{$archive.Dispose()}
}
function CopySourceToCheckout($Entries){
  foreach($entry in $Entries){
    $rel=[string]$entry.path
    $sourceFile=Join-Path $staged ($rel.Replace('/','\'))
    $target=Join-Path $Source ($rel.Replace('/','\'))
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $sourceFile -Destination $target -Force
  }
}
# v0.4.9.16: candidate validation may create a *development-only* Git checkpoint
# in the existing repo. Use an isolated index/worktree pointing at the validated
# stage: never checkout, reset, stage or commit onto the active main branch.
function WriteDevelopmentCheckpoint {
  $spec=$manifest.development_checkpoint
  if($null -eq $spec){return}
  $branch=[string]$spec.branch
  $parentBranch=[string]$spec.parent_branch
  $parentHash=[string]$spec.parent_commit
  Assert ($branch -match '^dev/v\d+\.\d+\.\d+(\.\d+)?$') 'Invalid development checkpoint ref'
  Assert ($parentBranch -eq 'main' -or $parentBranch -match '^dev/v\d+\.\d+\.\d+(\.\d+)?$') 'Invalid checkpoint parent ref'
  if($parentBranch -eq 'main'){
    # Source-only infrastructure releases validated from the promoted main
    # baseline do not need an intervening dev/vN ref or a downloadable bundle.
    Assert ([string]$manifest.release_track -eq 'infrastructure-source') 'Main-parent checkpoint only permitted for infrastructure source'
    Assert ($parentHash -eq [string]$manifest.baseline_commit) 'Main-parent checkpoint baseline mismatch'
    Assert ($oldHead -eq $parentHash) 'Main-parent checkpoint cannot move beyond validated HEAD'
  }
  Assert ($parentHash -match '^[0-9a-f]{40}$') 'Invalid checkpoint parent object'
  $parentRef='refs/heads/'+$parentBranch
  $branchRef='refs/heads/'+$branch
  $actualParent=(& $git -C $Source rev-parse --verify $parentRef | Out-String).Trim().ToLowerInvariant()
  Assert ($LASTEXITCODE -eq 0 -and $actualParent -eq $parentHash) 'Expected verified development parent is not present'
  $already=(& $git -C $Source show-ref --verify --quiet $branchRef);Assert ($LASTEXITCODE -ne 0) ('Development ref already exists: '+$branchRef)
  $previousIndex=[Environment]::GetEnvironmentVariable('GIT_INDEX_FILE','Process')
  $previousWork=[Environment]::GetEnvironmentVariable('GIT_WORK_TREE','Process')
  $index=Join-Path $job 'checkpoint.index'
  try{
    [Environment]::SetEnvironmentVariable('GIT_INDEX_FILE',$index,'Process')
    [Environment]::SetEnvironmentVariable('GIT_WORK_TREE',$staged,'Process')
    Run $git @('-C',$Source,'read-tree',$parentRef) 'Cannot initialize isolated development index'
    foreach($file in $manifest.files){Run $git @('-C',$Source,'add','--',[string]$file.path) 'Cannot stage development checkpoint payload'}
    $tree=(& $git -C $Source write-tree | Out-String).Trim().ToLowerInvariant()
    Assert ($LASTEXITCODE -eq 0 -and $tree -match '^[0-9a-f]{40}$') 'Cannot create isolated development tree'
    $checkpoint=(& $git -C $Source commit-tree $tree -p $parentHash -m ('Verified development candidate '+$release) | Out-String).Trim().ToLowerInvariant()
    Assert ($LASTEXITCODE -eq 0 -and $checkpoint -match '^[0-9a-f]{40}$') 'Cannot create development checkpoint commit'
  }finally{
    [Environment]::SetEnvironmentVariable('GIT_INDEX_FILE',$previousIndex,'Process')
    [Environment]::SetEnvironmentVariable('GIT_WORK_TREE',$previousWork,'Process')
  }
  # The zero old-id forbids overwriting an existing branch. No remote push,
  # production tag or active runtime activation occurs during Validate.
  Run $git @('-C',$Source,'update-ref',$branchRef,$checkpoint,('0'*40)) 'Cannot atomically install development checkpoint ref'
  Assert ((& $git -C $Source rev-parse HEAD | Out-String).Trim().ToLowerInvariant() -eq $oldHead) 'Main checkout changed during checkpoint creation'
  Write-Host ('RECOMPDEV_DEV_CHECKPOINT='+$branch)
  Write-Host ('RECOMPDEV_DEV_COMMIT='+$checkpoint)
  Write-Host 'RECOMPDEV_DEV_MAIN_UNCHANGED=TRUE'
}

function RestoreTransaction {
  if($runtimeTouched){
    foreach($item in $runtimeSnapshot){
      if($item.existed){
        New-Item -ItemType Directory -Path (Split-Path -Parent $item.path) -Force | Out-Null
        Copy-Item -LiteralPath $item.saved -Destination $item.path -Force
      }elseif(Test-Path -LiteralPath $item.path -PathType Leaf){
        Remove-Item -LiteralPath $item.path -Force
      }
    }
    if($stateBackup -and (Test-Path -LiteralPath $stateBackup)){
      Copy-Item -LiteralPath $stateBackup -Destination (Join-Path $runtimeRoot 'active-components.json') -Force
    }
  }
  if($madeTag){& $git -C $Source tag -d $tag | Out-Null; if($LASTEXITCODE -ne 0){throw 'Rollback failed: cannot remove release tag'}}
  if($changedSource -and -not $madeCommit){
    # Git add may have staged some files before a failed commit. Restore the
    # original index as well as original checkout file bytes.
    Run $git @('-C',$Source,'reset','--mixed',$oldHead) 'Git index rollback failed'
  }
  if($madeCommit){
    $current=(& $git -C $Source rev-parse HEAD | Out-String).Trim()
    Assert ($current -eq $newHead) 'Rollback refused: HEAD moved unexpectedly after release commit'
    Run $git @('-C',$Source,'reset','--hard',$oldHead) 'Git rollback failed'
  }
  if($changedSource){
    # Restore exact original checkout bytes (including local Git eol filters),
    # never an approximation reconstructed from newly extracted ZIP contents.
    foreach($entry in $sourceSnapshot){
      if($entry.existed){
        New-Item -ItemType Directory -Path (Split-Path -Parent $entry.path) -Force | Out-Null
        Copy-Item -LiteralPath $entry.saved -Destination $entry.path -Force
      }elseif(Test-Path -LiteralPath $entry.path){
        Remove-Item -LiteralPath $entry.path -Force
      }
    }
  }
}

New-Item -ItemType Directory -Path $job,$payload,$logDir,$backup -Force | Out-Null
Start-Transcript -Path $transcript -ErrorAction Stop | Out-Null
try {
  Write-Host 'RECOMPDEV_RELEASE_PROTOCOL=v1'
  Assert (-not $PublishOrigin -or $Mode -eq 'Install') '-PublishOrigin requires -Mode Install'
  Write-Host "RECOMPDEV_RELEASE_MODE=$Mode"
  Assert (Test-Path -LiteralPath $Source -PathType Container) 'RecompDev source checkout not found'
  Assert (Test-Path -LiteralPath $Package -PathType Leaf) 'Release ZIP not found'
  Assert ((Hash $Package) -eq $ExpectedSha256.ToLowerInvariant()) 'Package SHA-256 differs from independently supplied expected hash'
  $git=(Get-Command git.exe -ErrorAction Stop).Source
  $python=(Get-Command python.exe -ErrorAction Stop).Source
  $cmake=(Get-Command cmake.exe -ErrorAction Stop).Source
  $ctest=(Get-Command ctest.exe -ErrorAction Stop).Source
  $members=ExtractPackage $Package $payload
  $manifest=Get-Content -LiteralPath (Join-Path $payload 'release-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  Assert ($manifest.schema -eq 'recompdev-source-release-v1') 'Unknown release package schema'
  $release=[string]$manifest.release
  $tag=$release
  Assert ($release -match '^workspace/v\d+\.\d+\.\d+(\.\d+)?$') 'Invalid release identifier'
  Assert ([string]$manifest.baseline_commit -match '^[a-f0-9]{40}$') 'Invalid expected Git SHA-1'
  $oldHead=(& $git -C $Source rev-parse HEAD | Out-String).Trim().ToLowerInvariant()
  Assert ($LASTEXITCODE -eq 0) 'Cannot read local Git HEAD'
  Assert ($oldHead -eq [string]$manifest.baseline_commit) "Unexpected Git baseline: $oldHead instead of $($manifest.baseline_commit)"
  $baseTagHead=(& $git -C $Source rev-list -n 1 ([string]$manifest.baseline_tag) | Out-String).Trim().ToLowerInvariant()
  Assert ($LASTEXITCODE -eq 0 -and $baseTagHead -eq $oldHead) 'Baseline release tag does not match HEAD'
  $dirty=(& $git -C $Source status --porcelain --untracked-files=all | Out-String).Trim()
  Assert ($LASTEXITCODE -eq 0 -and -not $dirty) "Git checkout must be clean: $dirty"
  $tagFound=(& $git -C $Source tag -l $release | Out-String).Trim()
  Assert (-not $tagFound) "Release tag already exists: $release"
  Assert ($manifest.files.Count -gt 0 -and $manifest.files.Count -lt 500) 'Invalid changed file count'
  $listed=@{'release-manifest.json'=$true}
  foreach($entry in $manifest.files){
    $rel=[string]$entry.path
    ValidPath $rel
    $member='files/'+$rel
    Assert (-not $listed.ContainsKey($member)) "Duplicate manifest path: $rel"
    $listed[$member]=$true
    Assert ($members.ContainsKey($member)) "Missing packaged file: $rel"
    Assert ([string]$entry.new_sha256 -match '^[a-f0-9]{64}$') "Missing new SHA-256: $rel"
    $packed=Join-Path $payload ($member.Replace('/','\'))
    Assert ((Hash $packed) -eq [string]$entry.new_sha256) "Package payload hash mismatch: $rel"
    Assert ((Get-Item -LiteralPath $packed).Length -eq [long]$entry.bytes) "Package payload byte count mismatch: $rel"
    if($rel -match '\.md$'){
      # Reject binary Mega Drive .md images while allowing Markdown documentation.
      Assert ([long]$entry.bytes -le 8388608) "Markdown source exceeds 8 MiB: $rel"
      $utf8Strict=[Text.UTF8Encoding]::new($false,$true)
      try{$markdownText=$utf8Strict.GetString([IO.File]::ReadAllBytes($packed))}
      catch{throw "Markdown source is not UTF-8 text: $rel"}
      Assert ($markdownText.IndexOf([char]0) -lt 0) "Binary NUL in Markdown source: $rel"
    }
  }
  Assert ($listed.Count -eq $members.Count) 'ZIP contains undeclared payload files'
  # One-time bootstrap from Downloads is allowed, but only if it exactly matches
  # the SHA-256-pinned script inside this independently hash-pinned release ZIP.
  $selfRel='files/Install-RecompDev-Release.ps1'
  if($members.ContainsKey($selfRel)){
    $runningScript=[IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)
    $rootInstaller=[IO.Path]::GetFullPath((Join-Path $Source 'Install-RecompDev-Release.ps1'))
    if($runningScript -ne $rootInstaller){
      # First-time bootstrap is trusted only when byte-identical to the
      # independently SHA-256-pinned installer in the source release ZIP.
      Assert ((Hash $runningScript) -eq (Hash (Join-Path $payload 'files\Install-RecompDev-Release.ps1'))) 'Bootstrap script differs from package-pinned installer'
    }
    # Future installer upgrades run from the existing Git-tracked root script;
    # the full package SHA and clean committed baseline authenticate the update.
  }
  if($Mode -eq 'Install'){
    Assert ($manifest.promotion_eligible -eq $true) ('Release is CANDIDATE/BLOCKED: '+[string]$manifest.promotion_blocker)
    Assert (@($manifest.required_acceptance_tests).Count -gt 0) 'Promotion requires explicit named acceptance tests'
    # Never interpret an infrastructure-source release as native-game qualification.
    Assert ([string]$manifest.release_track -eq 'infrastructure-source') 'This installer requires a separately qualified release track for runtime activation'
    Assert ([string]$manifest.promotion_scope -eq 'git-main-only-no-runtime') 'Ambiguous infrastructure promotion scope'
    Assert ($manifest.gameplay_qualified -eq $false) 'Infrastructure release must not claim gameplay qualification'
  }
  Write-Host "RECOMPDEV_RELEASE_TARGET=$release"
  Write-Host 'RECOMPDEV_PHASE=CANONICAL_GIT_STAGING'
  Run $git @('-C',$Source,'archive','--format=zip',"--output=$baseZip",'HEAD') 'Git baseline archive failed'
  # Git archive contains only committed files; unzip into external staging, then
  # canonicalise each replaced path from the actual raw Git blob below.
  Expand-Archive -LiteralPath $baseZip -DestinationPath $staged -Force
  Write-Host 'RECOMPDEV_PHASE=RESTORE_MANIFEST_DECLARED_HISTORY'
  RestoreManifestDeclaredHistoricalFiles
  foreach($entry in $manifest.files){
    $rel=[string]$entry.path
    $dst=Join-Path $staged ($rel.Replace('/','\'))
    if($null -ne $entry.old_sha256){
      Assert ([string]$entry.old_sha256 -match '^[a-f0-9]{64}$') "Invalid expected committed hash: $rel"
      $canonical=Join-Path $job ('git-blob\'+$rel.Replace('/','\'))
      GitBlobToFile $rel $canonical
      Assert ((Hash $canonical) -eq [string]$entry.old_sha256) "Committed source hash mismatch: $rel"
      if((Hash $dst) -ne [string]$entry.old_sha256){Copy-Item -LiteralPath $canonical -Destination $dst -Force}
    }else{Assert (-not (Test-Path -LiteralPath $dst)) "Expected added file already exists: $rel"}
    New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $payload ('files\'+$rel.Replace('/','\'))) -Destination $dst -Force
    Assert ((Hash $dst) -eq [string]$entry.new_sha256) "Staged source hash mismatch: $rel"
  }
  $env:PYTHONDONTWRITEBYTECODE='1'
  Push-Location $staged
  try{
    Write-Host 'RECOMPDEV_PHASE=DOCS_AND_PYTHON_TESTS'
    Run $python @('-B','-m','workspace.docs_governance','check','--release',$release) 'Documentation governance failed'
    Run $python @('-B','-m','unittest','discover','-s','workspace/tests','-q') 'Workspace tests failed'
    Run $python @('-B','-m','unittest','discover','-s','discovery_integration/tests','-q') 'Historical discovery integration tests failed'
    Run $python @('-B','-m','unittest','discover','-s','release/tests','-q') 'Release protocol tests failed'
    Write-Host 'RECOMPDEV_PHASE=HISTORICAL_PRESERVATION'
    Run $python @('-B','migration/controller.py','verify') 'Historical 642-file preservation failed'
    Write-Host 'RECOMPDEV_PHASE=NATIVE_BUILD'
    Run $cmake @('-S',(Join-Path $staged 'harness'),'-B',$cmakeBuild) 'CMake configure failed'
    Run $cmake @('--build',$cmakeBuild,'--config','Release','--parallel','4') 'Native build failed'
    Write-Host 'RECOMPDEV_PHASE=FULL_CTEST'
    if($Mode -eq 'Install'){
      $registered=(& $ctest --test-dir $cmakeBuild -C Release -N | Out-String)
      Assert ($LASTEXITCODE -eq 0) 'Cannot list registered acceptance tests'
      foreach($must in $manifest.required_acceptance_tests){
        $testName=[string]$must
        Assert ($testName -match '^[a-zA-Z0-9_]+$') "Invalid acceptance test name: $testName"
        $pattern='(?m)^\s*Test\s+#\d+:\s+'+[regex]::Escape($testName)+'\s*$'
        Assert ($registered -match $pattern) "Required acceptance test is not registered: $testName"
      }
    }
    Run $ctest @('--test-dir',$cmakeBuild,'-C','Release','--output-on-failure','--parallel','4') 'Native CTest suite failed'
  }finally{Pop-Location}
  $binDir=Join-Path $cmakeBuild 'bin\Release'
  if(-not (Test-Path -LiteralPath (Join-Path $binDir 'RecompDev.exe'))){$binDir=Join-Path $cmakeBuild 'bin'}
  Assert (Test-Path -LiteralPath (Join-Path $binDir 'RecompDev.exe')) 'Compiled native controller missing'
  $inventory=@()
  foreach($component in $manifest.binary_components){
    $name=[string]$component.name
    Assert ($name -match '^(controller|rd_[a-z0-9_]+)$') 'Invalid compiled module name'
    $filename=if($name -eq 'controller'){'RecompDev.exe'}else{$name+'.dll'}
    $built=Join-Path $binDir $filename
    Assert (Test-Path -LiteralPath $built -PathType Leaf) "Missing compiled target: $filename"
    $inventory+= [pscustomobject]@{component=$name;version=[string]$component.version;file=$filename;sha256=(Hash $built);path=$built}
  }
  $inventoryFile=Join-Path $job 'native-binary-hashes.json'
  [IO.File]::WriteAllText($inventoryFile,($inventory|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
  Write-Host "RECOMPDEV_BINARY_HASHES=$inventoryFile"
  # Independent native tools are source-only build outputs: attest them without
  # adding them to the production runtime lockfile or active DLL inventory.
  if($null -ne $manifest.PSObject.Properties['auxiliary_binaries']){
    $auxiliary=@()
    foreach($spec in $manifest.auxiliary_binaries){
      $name=[string]$spec.name
      $role=[string]$spec.role
      Assert ($name -match '^[A-Za-z][A-Za-z0-9_]+\.exe$') "Unsafe auxiliary binary name: $name"
      Assert ($role -match '^[a-z][a-z0-9_-]+$') "Unsafe auxiliary binary role: $role"
      $built=Join-Path $binDir $name
      Assert (Test-Path -LiteralPath $built -PathType Leaf) "Missing auxiliary compiled target: $name"
      $auxiliary+= [pscustomobject]@{role=$role;file=$name;sha256=(Hash $built);path=$built}
    }
    $auxiliaryFile=Join-Path $job 'auxiliary-binary-hashes.json'
    [IO.File]::WriteAllText($auxiliaryFile,($auxiliary|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
    Write-Host "RECOMPDEV_AUXILIARY_BINARY_HASHES=$auxiliaryFile"
  }
  Write-Host 'RECOMPDEV_TESTS=PASS'
  if($Mode -eq 'Validate'){
    Write-Host 'RECOMPDEV_PHASE=DEV_CHECKPOINT'
    WriteDevelopmentCheckpoint
    Write-Host ('RECOMPDEV_CANDIDATE_RESULT=VALIDATED_NOT_INSTALLED')
    Write-Host ('RECOMPDEV_PROMOTION_STATUS='+[string]$manifest.promotion_blocker)
    Write-Host 'RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED=TRUE'
    $releaseOk=$true
  }elseif($manifest.release_track -eq 'infrastructure-source'){
    # v0.4.9.17: infrastructure source promotion is deliberately separate from
    # game runtime qualification. This transaction never copies EXEs/DLLs or
    # updates active-components.json. Build artifacts remain in release evidence.
    Write-Host 'RECOMPDEV_PHASE=INFRASTRUCTURE_SOURCE_PROMOTION'
    $stateFile=Join-Path $runtimeRoot 'active-components.json'
    $stateHash=if(Test-Path -LiteralPath $stateFile -PathType Leaf){Hash $stateFile}else{''}
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    foreach($entry in $manifest.files){
      $rel=[string]$entry.path
      $target=Join-Path $Source ($rel.Replace('/','\'))
      $exists=Test-Path -LiteralPath $target -PathType Leaf
      $saved=Join-Path $backup ('source\'+$rel.Replace('/','\'))
      if($exists){
        New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
        Copy-Item -LiteralPath $target -Destination $saved -Force
      }
      $sourceSnapshot+= [pscustomobject]@{path=$target;existed=$exists;saved=$saved}
    }
    $changedSource=$true
    CopySourceToCheckout $manifest.files
    foreach($entry in $manifest.files){Run $git @('-C',$Source,'add','--',[string]$entry.path) 'Cannot stage infrastructure source'}
    Run $git @('-C',$Source,'commit','-m',([string]$manifest.commit_message)) 'Infrastructure source commit failed'
    $madeCommit=$true
    $newHead=(& $git -C $Source rev-parse HEAD | Out-String).Trim()
    Assert ($LASTEXITCODE -eq 0 -and $newHead -ne $oldHead) 'Source promotion did not create a commit'
    Run $git @('-C',$Source,'tag','-a',$tag,'-m',('Validated infrastructure source '+$tag)) 'Infrastructure tag failed'
    $madeTag=$true
    $gitBundle=Join-Path $archiveRoot ('git-backups\'+($tag.Replace('/','_'))+'-'+$newHead.Substring(0,12)+'.bundle')
    New-Item -ItemType Directory -Path (Split-Path -Parent $gitBundle) -Force | Out-Null
    Run $git @('-C',$Source,'bundle','create',$gitBundle,'--all') 'Source rollback backup failed'
    Run $git @('-C',$Source,'bundle','verify',$gitBundle) 'Source rollback backup invalid'
    Assert ((& $git -C $Source rev-list -n 1 $tag | Out-String).Trim() -eq $newHead) 'Infrastructure Git tag mismatch'
    Assert ((& $git -C $Source status --porcelain --untracked-files=all | Out-String).Trim() -eq '') 'Checkout dirty following infrastructure promotion'
    Assert ($(if(Test-Path -LiteralPath $stateFile -PathType Leaf){Hash $stateFile}else{''}) -eq $stateHash) 'Active runtime lockfile changed unexpectedly'
    Write-Host 'RECOMPDEV_RELEASE_RESULT=INFRASTRUCTURE_SOURCE_INSTALLED'
    Write-Host 'RECOMPDEV_RUNTIME_QUALIFIED=FALSE'
    Write-Host 'RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED=TRUE'
    Write-Host "RECOMPDEV_GIT_COMMIT=$newHead"
    Write-Host "RECOMPDEV_GIT_TAG=$tag"
    Write-Host "RECOMPDEV_GIT_BACKUP=$gitBundle"
    $releaseOk=$true
  }else{
    Write-Host 'RECOMPDEV_PHASE=ACTIVATE_AFTER_TESTS'
    $stateFile=Join-Path $runtimeRoot 'active-components.json'
    Assert (Test-Path -LiteralPath $stateFile -PathType Leaf) 'Missing compiled runtime lockfile'
    $state=Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert ($state.schema -eq 'recompdev-runtime-lock-v1') 'Unexpected runtime lockfile schema'
    Assert ($null -ne $state.active.PSObject.Properties['controller']) 'Runtime lockfile lacks canonical controller entry'
    Assert ($null -eq $state.active.PSObject.Properties['RecompDev']) 'Runtime lockfile uses unexpected executable-name key'
    Assert (@($manifest.binary_components | Where-Object { $_.name -eq 'controller' }).Count -eq 1) 'Release manifest must identify controller by canonical lockfile key'
    foreach($p in $state.active.PSObject.Properties){
      $loc=[string]$p.Value.active_path
      Assert ((Hash $loc) -eq [string]$p.Value.sha256) "Existing active binary changed: $($p.Name)"
    }
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    $stateBackup=Join-Path $backup 'active-components.json'
    Copy-Item -LiteralPath $stateFile -Destination $stateBackup -Force
    foreach($module in $inventory){
      $target=if($module.component -eq 'controller'){Join-Path $runtimeRoot $module.file}else{Join-Path $runtimeRoot ('active\'+$module.file)}
      $exists=Test-Path -LiteralPath $target -PathType Leaf
      $saved=Join-Path $backup ('runtime\'+$module.file)
      if($exists){New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null;Copy-Item -LiteralPath $target -Destination $saved -Force}
      $runtimeSnapshot+= [pscustomobject]@{path=$target;existed=$exists;saved=$saved}
    }
    # Snapshot checkout bytes first; CRLF checkout filters must be reversible.
    foreach($entry in $manifest.files){
      $rel=[string]$entry.path
      $target=Join-Path $Source ($rel.Replace('/','\'))
      $existed=Test-Path -LiteralPath $target -PathType Leaf
      $saved=Join-Path $backup ('source\'+$rel.Replace('/','\'))
      if($existed){
        New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
        Copy-Item -LiteralPath $target -Destination $saved -Force
      }
      $sourceSnapshot+= [pscustomobject]@{path=$target;existed=$existed;saved=$saved}
    }
    # Copy only manifest-declared files, then commit and tag only after all tests.
    $changedSource=$true  # set before copying, so partial copy is rollback-safe
    CopySourceToCheckout $manifest.files
    foreach($entry in $manifest.files){Run $git @('-C',$Source,'add','--',[string]$entry.path) 'Git add failed'}
    Run $git @('-C',$Source,'commit','-m',([string]$manifest.commit_message)) 'Git release commit failed'
    $madeCommit=$true
    $newHead=(& $git -C $Source rev-parse HEAD | Out-String).Trim()
    Assert ($LASTEXITCODE -eq 0) 'Unable to read release commit'
    Run $git @('-C',$Source,'tag','-a',$tag,'-m',('Validated '+$tag)) 'Git tag failed'
    $madeTag=$true
    $gitBundle=Join-Path $archiveRoot ('git-backups\'+($tag.Replace('/','_'))+'-'+$newHead.Substring(0,12)+'.bundle')
    New-Item -ItemType Directory -Path (Split-Path -Parent $gitBundle) -Force | Out-Null
    Run $git @('-C',$Source,'bundle','create',$gitBundle,'--all') 'Git backup failed'
    Run $git @('-C',$Source,'bundle','verify',$gitBundle) 'Git backup verification failed'
    $runtimeTouched=$true
    foreach($module in $inventory){
      $target=if($module.component -eq 'controller'){Join-Path $runtimeRoot $module.file}else{Join-Path $runtimeRoot ('active\'+$module.file)}
      $store=Join-Path $runtimeRoot ('versions\'+$module.component+'\'+$module.version+'\'+$module.file)
      New-Item -ItemType Directory -Path (Split-Path -Parent $store) -Force | Out-Null
      if(Test-Path -LiteralPath $store){Assert ((Hash $store) -eq $module.sha256) "Immutable version conflict: $($module.component)"}
      else{Copy-Item -LiteralPath $module.path -Destination $store -Force}
      New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
      Copy-Item -LiteralPath $store -Destination $target -Force
      Assert ((Hash $target) -eq $module.sha256) "Binary activation mismatch: $($module.file)"
      $prior=$state.active.PSObject.Properties[$module.component]
      if($null -ne $prior){
        if($null -eq $state.history.PSObject.Properties[$module.component]){$state.history | Add-Member -NotePropertyName $module.component -NotePropertyValue @()}
        $state.history.($module.component)= @($state.history.($module.component)) + @($prior.Value)
      }
      $scope=if($module.component -eq 'controller'){'production-entrypoint'}else{'harness'}
      $newValue=[pscustomobject]@{version=$module.version;sha256=$module.sha256;binary=$store;active_path=$target;scope=$scope;git_commit=$newHead}
      if($null -ne $prior){$state.active.($module.component)=$newValue}
      else{$state.active | Add-Member -NotePropertyName $module.component -NotePropertyValue $newValue}
    }
    $nextState=Join-Path $backup 'active-components.next.json'
    [IO.File]::WriteAllText($nextState,($state | ConvertTo-Json -Depth 15),[Text.UTF8Encoding]::new($false))
    Copy-Item -LiteralPath $nextState -Destination $stateFile -Force
    foreach($module in $inventory){
      Assert ((Hash ([string]$state.active.($module.component).active_path)) -eq $module.sha256) "Post-activation hash mismatch: $($module.file)"
    }
    # Complete the transaction only when Git, tag, runtime lockfile and each
    # activated binary agree. Never print INSTALLED for a partial deployment.
    $finalHead=(& $git -C $Source rev-parse HEAD | Out-String).Trim()
    Assert ($LASTEXITCODE -eq 0 -and $finalHead -eq $newHead) 'Release Git HEAD verification failed'
    $finalTag=(& $git -C $Source rev-list -n 1 $tag | Out-String).Trim()
    Assert ($LASTEXITCODE -eq 0 -and $finalTag -eq $newHead) 'Release Git tag verification failed'
    $finalDirty=(& $git -C $Source status --porcelain --untracked-files=all | Out-String).Trim()
    Assert ($LASTEXITCODE -eq 0 -and -not $finalDirty) "Checkout dirty following source commit: $finalDirty"
    $installedLock=Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach($module in $inventory){
      $locked=$installedLock.active.PSObject.Properties[$module.component]
      Assert ($null -ne $locked) "Missing installed lockfile component: $($module.component)"
      Assert ([string]$locked.Value.version -eq $module.version) "Installed version mismatch: $($module.component)"
      Assert ([string]$locked.Value.git_commit -eq $newHead) "Installed component commit mismatch: $($module.component)"
      Assert ((Hash ([string]$locked.Value.active_path)) -eq $module.sha256) "Installed component hash mismatch: $($module.component)"
    }
    Write-Host "RECOMPDEV_RELEASE_RESULT=INSTALLED"
    Write-Host "RECOMPDEV_GIT_TAG=$tag"
    Write-Host "RECOMPDEV_GIT_COMMIT=$newHead"
    Write-Host "RECOMPDEV_GIT_BACKUP=$gitBundle"
    $releaseOk=$true
  }
} catch {
  Write-Host "RECOMPDEV_RELEASE_FAILED=$($_.Exception.Message)"
  if($changedSource -or $runtimeTouched){
    try{RestoreTransaction;Write-Host 'RECOMPDEV_ROLLBACK=SUCCESS'}
    catch{Write-Host "RECOMPDEV_ROLLBACK=FAILED_REQUIRES_MANUAL_RECOVERY: $($_.Exception.Message)"}
  }
  if(-not $changedSource -and -not $runtimeTouched){Write-Host 'RECOMPDEV_ACTIVE_RUNTIME_UNCHANGED=TRUE'}
  throw
 } finally {
  Write-Host "RECOMPDEV_RELEASE_EVIDENCE=$job"
  Write-Host "RECOMPDEV_RELEASE_LOG=$transcript"
  # Installation's remote publication and generated-history restoration run
  # ONLY after local commit, immutable tag and rollback bundle verification.
  if(-not ($Mode -eq 'Install' -and $releaseOk)){Stop-Transcript | Out-Null}
}

if($Mode -eq 'Install' -and $releaseOk){
  # Source-only and runtime releases must both preserve per-game generated Git
  # histories. Never allow a GitHub outage to undo a verified local release.
  Write-Host 'RECOMPDEV_PHASE=GENERATED_SOURCE_RESTORE_AFTER_INSTALL'
  try {
    $syncScript=Join-Path $Source 'analysis_integration\generated_source_sync.py'
    Assert (Test-Path -LiteralPath $syncScript -PathType Leaf) 'Generated source sync helper not installed'
    $generatedHome=if($env:RECOMPDEV_HOME){$env:RECOMPDEV_HOME}else{Join-Path $env:LOCALAPPDATA 'RecompDev'}
    $settingsFile=Join-Path $generatedHome 'generated-source-sync.json'
    $defaultShared=Join-Path $projectParent 'RecompDev-plugins'
    if(-not (Test-Path -LiteralPath $settingsFile -PathType Leaf)){
      if(Test-Path -LiteralPath (Join-Path $defaultShared '.git') -PathType Container){
        & $python $syncScript setup --home $generatedHome --repository $defaultShared
        Assert ($LASTEXITCODE -eq 0) 'Generated source synchroniser setup failed'
      }else{
        Write-Host 'RECOMPDEV_GENERATED_SOURCE_RESTORE=SKIPPED_REPOSITORY_NOT_CONFIGURED'
      }
    }
    if(Test-Path -LiteralPath $settingsFile -PathType Leaf){
      & $python $syncScript restore-all --home $generatedHome
      Assert ($LASTEXITCODE -eq 0) 'Generated source restore incomplete'
      Write-Host 'RECOMPDEV_GENERATED_SOURCE_RESTORE=VERIFIED'
      # The first v28 installation migrates the two pre-v28 unsquashed ROM
      # subtrees and publishes SHA-qualified source provenance on the one main
      # branch. Failure stays pending; the restored local history is safe.
      & $python $syncScript publish --home $generatedHome
      if($LASTEXITCODE -ne 0){Write-Host 'RECOMPDEV_GENERATED_SOURCE_PUBLICATION=PENDING_RETRY'}
      else{Write-Host 'RECOMPDEV_GENERATED_SOURCE_PUBLICATION=VERIFIED'}
    }
  }catch{
    Write-Host 'RECOMPDEV_GENERATED_SOURCE_RESTORE=PENDING_RETRY_LOCAL_RELEASE_UNCHANGED'
    Write-Host ("RECOMPDEV_GENERATED_SOURCE_RESTORE_REASON="+$_.Exception.Message)
  }

  # Never force-push or publish any game-derived source to the public
  # controller repository. This phase publishes only the controller release.
  if($PublishOrigin){
    Write-Host 'RECOMPDEV_PHASE=ORIGIN_PUBLISH_AFTER_LOCAL_COMMIT_TAG_BACKUP'
    try {
      Assert ($madeCommit -and $madeTag -and $newHead) 'Release commit/tag missing before remote publication'
      $branch=(& $git -C $Source symbolic-ref --short HEAD | Out-String).Trim()
      Assert ($LASTEXITCODE -eq 0 -and $branch -eq 'main') 'Remote publishing requires canonical main'
      $current=(& $git -C $Source rev-parse HEAD | Out-String).Trim().ToLowerInvariant()
      Assert ($LASTEXITCODE -eq 0 -and $current -eq $newHead.ToLowerInvariant()) 'HEAD changed before publication'
      $tagCommit=(& $git -C $Source rev-list -n 1 $tag | Out-String).Trim().ToLowerInvariant()
      Assert ($LASTEXITCODE -eq 0 -and $tagCommit -eq $current) 'Release tag no longer points to HEAD'
      Assert ((& $git -C $Source status --porcelain --untracked-files=all | Out-String).Trim() -eq '') 'Source checkout dirty'
      $remoteTag=(& $git -C $Source ls-remote --tags origin ('refs/tags/'+$tag) | Out-String).Trim()
      Assert ($LASTEXITCODE -eq 0 -and -not $remoteTag) 'Release tag already exists on origin'
      Run $git @('-C',$Source,'push','--atomic','origin',
        'HEAD:refs/heads/main',('refs/tags/'+$tag+':refs/tags/'+$tag)) 'Atomic origin push failed'
      $remoteRefs=@(& $git -C $Source ls-remote origin 'refs/heads/main' ('refs/tags/'+$tag+'^{}'))
      Assert ($LASTEXITCODE -eq 0) 'Remote verification failed'
      $mainRef=($remoteRefs | Where-Object { $_ -match '[\s]refs/heads/main$' } | Select-Object -First 1)
      $peeledRef=($remoteRefs | Where-Object { $_ -match ('[\s]refs/tags/'+[regex]::Escape($tag)+'\^\{\}$') } | Select-Object -First 1)
      Assert ($mainRef -and $peeledRef) 'Missing origin main or release tag'
      Assert (($mainRef -split '\s+')[0].ToLowerInvariant() -eq $current) 'Origin main mismatch'
      Assert (($peeledRef -split '\s+')[0].ToLowerInvariant() -eq $current) 'Origin tag mismatch'
      Write-Host 'RECOMPDEV_REMOTE_PROMOTION=PUBLISHED'
      Write-Host "RECOMPDEV_REMOTE_MAIN_COMMIT=$current"
      Write-Host "RECOMPDEV_REMOTE_TAG=$tag"
    } catch {
      Write-Host 'RECOMPDEV_REMOTE_PROMOTION=PENDING_LOCAL_RELEASE_REMAINS_INSTALLED'
      Write-Host ("RECOMPDEV_REMOTE_FAILURE="+$_.Exception.Message)
    }
  }
  Stop-Transcript | Out-Null
}
