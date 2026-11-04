param([switch]$Full)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  Write-Host 'v0.4.0.39 [1/4] SHA-256 release integrity'
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0439.json
  if($LASTEXITCODE -ne 0){throw 'Release SHA verification failed'}
  Write-Host 'v0.4.0.39 [2/4] Independently checked compiled framebuffer and PCM output'
  & py -3 tools/Validate-Native-Outputs-v0437.py
  if($LASTEXITCODE -ne 0){throw 'Compiled native-output check failed'}
  Write-Host 'v0.4.0.39 [3/4] Compiled Z80/host semantics and source-provenance regressions'
  foreach($name in @('test_shared_catalogue_v0439.py','test_conditional_control_dev.py','test_sms_th_feedback_dev.py','test_right_shift_v0439.py','test_native_screen_v0439.py','test_release_v0438.py','test_release_v0437.py')){
    & py -3 -m unittest discover -s tests -p $name -q
    if($LASTEXITCODE -ne 0){throw "Failed regression: $name"}
  }
  Write-Host 'v0.4.0.39 [4/4] Cross-component bridge suite'
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge tests failed'}
  if($Full){
    Write-Host 'FULL REPOSITORY SUITE REQUESTED (may run for an extended time)'
    $tests=Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name
    foreach($test in $tests){
      Write-Host "FULL TEST: $($test.Name)"
      & py -3 -m unittest discover -s tests -p $test.Name -q
      if($LASTEXITCODE -ne 0){throw "Full test failed: $($test.Name)"}
    }
  }
  Write-Host 'PASS: v0.4.0.39 focused correctness, native output and bridge qualification.'
  if(-not $Full){Write-Warning 'Full repository suite NOT run. For broader acceptance use Verify-v0439.ps1 -Full.'}
  Write-Warning 'Authentic seven-game reference parity, Windows GUI performance and gameplay are NOT established by verification.'
} finally {Pop-Location}
