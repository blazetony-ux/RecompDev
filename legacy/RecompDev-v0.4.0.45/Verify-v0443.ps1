param([switch]$Full)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root
try {
  Write-Host 'v0.4.0.43 [1/4] Release SHA-256 integrity'
  & py -3 tools/Verify-Release-Hashes.py --root . --manifest FILE_SHA256_v0443.json
  if($LASTEXITCODE -ne 0){throw 'Release integrity failed'}
  Write-Host 'v0.4.0.43 [2/4] Compiled framebuffer and PCM contract'
  & py -3 tools/Validate-Native-Outputs-v0437.py
  if($LASTEXITCODE -ne 0){throw 'Native output fixture failed'}
  Write-Host 'v0.4.0.43 [3/4] Compiled CPU and recovery/campaign regressions'
  $tests=@('test_release_v0441.py','test_interaction_refresh_v0441.py','test_generated_start_replay_v0441.py','test_sms_pause_nmi_v0441.py','test_native_interaction_v0441.py','test_verification_discovery_v0442.py','test_release_v0443.py','test_verified_coverage_v0443.py','test_sms_psg_v0443.py','test_native_frame_timeline_v0443.py','test_recovery_profiler_v0443.py','test_generated_snapshots_v0443.py','test_shared_catalogue_v0439.py','test_windows_native_stack_v0440.py','test_native_process_exit_v0440.py','test_staged_recovery_v0440.py','test_continuous_recovery_v0435.py','test_campaign_comparison_v0438.py','test_conditional_control_dev.py','test_sms_th_feedback_dev.py','test_right_shift_v0439.py','test_native_screen_v0439.py','test_release_v0438.py','test_release_v0437.py')
  & py -3 tools/Verify-Test-Discovery-v0442.py --folder tests --patterns $tests
  if($LASTEXITCODE -ne 0){throw 'Release test discovery preflight failed'}
  foreach($name in $tests) {
    & py -3 -m unittest discover -s tests -p $name -q
    if($LASTEXITCODE -ne 0){throw "Regression failed: $name"}
  }
  Write-Host 'v0.4.0.43 [4/4] Cross-component bridge checks'
  & py -3 tools/Verify-Test-Discovery-v0442.py --folder bridge/tests --patterns 'test_*.py'
  if($LASTEXITCODE -ne 0){throw 'Bridge test discovery preflight failed'}
  & py -3 -m unittest discover -s bridge/tests -p 'test_*.py' -q
  if($LASTEXITCODE -ne 0){throw 'Bridge regressions failed'}
  if($Full){
    Write-Host 'FULL REPOSITORY SUITE REQUESTED'
    foreach($test in (Get-ChildItem (Join-Path $root 'tests') -Filter 'test_*.py' -File | Sort-Object Name)){
      & py -3 tools/Verify-Test-Discovery-v0442.py --folder tests --patterns $test.Name
      if($LASTEXITCODE -ne 0){throw "Full suite test discovery failed: $($test.Name)"}
      & py -3 -m unittest discover -s tests -p $test.Name -q
      if($LASTEXITCODE -ne 0){throw "Full suite failed: $($test.Name)"}
    }
  }
  Write-Host 'PASS: v0.4.0.43 focused correctness, recovery, output and bridge checks.'
  if(-not $Full){Write-Warning 'Full repository suite NOT run; use Verify-v0443.ps1 -Full for broader local acceptance.'}
  Write-Warning 'Windows real-game, MAME parity and playability remain unverified by synthetic tests.'
} finally {Pop-Location}
