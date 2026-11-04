# RecompDev v0.4.0.24 — Integrated Native Campaign & Evidence

## What is new

This release connects the **existing real source-attested Z80 native recovery/compiler** to the **existing compiled continuous game host** using one user-invoked, bounded campaign. It does not replace either with a Z80 interpreter. The common coordinator uses an explicit system-to-host adapter registry. Other unsupported systems fail closed and cannot accidentally run Master System semantics.

- `tools/Run-Integrated-Native.py`: a single command which authenticates the original library ROM against the catalogue SHA-256, invokes the native bank-aware pilot and automatic bounded recovery, verifies full event chunks, runs the generated continuous application, re-verifies frame/audio hashes and emits `campaign-result.json` with clear stop reasons. A second headless replay confirms reproducibility; `--window` uses the experimental Windows host with live keyboard input and does not claim determinism.
- `platform424/evidence.py`: bounded read-only reconciliation of source-hash-matched older native pilot reports, with chunk SHA-256 validation and rejection of tampered stream data. Later integrated campaigns are also indexed. No ROM bytes are copied into this index.
- `/tooling`: the prior v0.4.0.21 labels are corrected and a new Source-linked native evidence section displays historical per-game pilot progress with recorded provenance. Source-hash linking does **not** magically transform native-pilot statistics into verified game correctness.
- v0.4.0.23 Windows verification hotfix is included: the six-instruction baseline test isolates autonomous recovery and the bank recovery suite no longer accidentally re-runs imported tests.
- Versioned catalogue and native job paths are isolated; previous installations remain untouched.

## What has **not** been achieved

No full commercial game was reproduced or independently matched in the developer environment. Authentic MAME/native execution-state synchronisation, production semantic self-repair, accurate hardware timing and Shinobi gameplay remain **unqualified**. The enhanced coordinator uses the existing Z80 backend; it does not claim increased complete Z80 opcode coverage or a production-ready second-ISA host. These are explicit future release blockers, not hidden successes.

## Installation — PowerShell one-liners

Close the old Workbench. Download `RecompDev-v0.4.0.24-Integrated-Native-Campaign.zip` to Downloads.

**Extract**:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.24-Integrated-Native-Campaign.zip" -DestinationPath 'C:\Projects' -Force
```

**Full verification (runs the new compiled gate and all regression suites)**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.24\Verify-v0424.ps1'
```

**Launch Workbench**:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.24\Run-Workbench.ps1'
```

## Owner-controlled authentic Shinobi experiment

Once full verification passes, and if the same Shinobi ROM is already imported and prepared in the inherited catalogue, this one-liner runs the integrated native campaign, including the source/hash check, bank recovery and live Windows native application. It does not demand a separate old 500K-only pilot. **The native game may display nothing or stop with a code/hardware blocker; this is a diagnostic outcome, not a playable port.**

```powershell
$r='C:\Projects\RecompDev-v0.4.0.24'; py -3 "$r\tools\Run-Integrated-Native.py" --db "$r\catalogue.v0424-working.sqlite" --source-id 'dac4f1dcb41193cb42a96950444a87c5f2952ea66474c59a38c07b10ac411e47' --rom-root 'C:\Roms' --output-root "$r\evidence\integrated-native-v0424\jobs" --steps 500000 --frames 120 --recoveries 2 --window
```

If the catalogue has no prepared source, use the existing Autonomous Discovery / Prepare controls. Do not bypass the source SHA-256 check. `--window` is optional; omitting it enables two deterministic headless runs and verifies both outputs.

**Collect the latest campaign evidence (preserves the event-stream hierarchy, excludes all `native-project` directories and ROM files):**

```powershell
$r='C:\Projects\RecompDev-v0.4.0.24'; $j=Get-ChildItem "$r\evidence\integrated-native-v0424\jobs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if(-not $j){throw 'No integrated job found'}; $stage=Join-Path $env:TEMP "RecompDev-v0424-Evidence-$($j.Name)"; New-Item -ItemType Directory -Path $stage -Force | Out-Null; Copy-Item -LiteralPath $j.FullName -Destination $stage -Recurse -Force; Get-ChildItem $stage -Directory -Recurse | Where-Object {$_.Name -eq 'native-project'} | Remove-Item -Recurse -Force; $zip="$env:USERPROFILE\Desktop\RecompDev-v0424-Integrated-Evidence.zip"; Compress-Archive -Path "$stage\*" -DestinationPath $zip -Force; Remove-Item $stage -Recurse -Force; Write-Host "Evidence: $zip"
```

The archive contains only diagnostic artifacts and no game ROM. This is evidence packaging, not automatic external parity qualification.

## Test boundary

Synthetic tests prove both success (native video/audio frames and deterministic output) and honest native-code boundaries, plus source and event/asset tamper rejection. Windows/MSVC compilation and live GUI playback are *not* claimed from Linux tests; run `Verify-v0424.ps1` on the owner machine and report its results. This is a platform-wide improvement to the workflow; the only Shinobi-specific element is the **example invocation's source hash**, not shared program logic.
