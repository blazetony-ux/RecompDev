# RecompDev v0.4.0.13 — Independent Emulator Observations and First-Divergence Diagnostics

**Purpose:** reusable, source-attested game recompilation tooling. The native code generator still supports only experimental Z80/Master System C++ execution. There is no playable-game or native 68000/MIPS qualification in this version. No ROMs, commercial binaries, MAME executable or emulator BIOS are bundled.

## Installation — PowerShell one-liners

Close the old Workbench. Download `RecompDev-v0.4.0.13-External-Oracle-Diagnostics.zip` into Downloads.

**1. Extract**

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.13-External-Oracle-Diagnostics.zip" -DestinationPath 'C:\Projects' -Force
```

**2. Launch**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.13\Run-Workbench.ps1'
```

**3. Verify (optional, may be long)**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.13\Verify-v0413.ps1'
```

The new working catalogue is `catalogue.v0413-working.sqlite`, initialised from your most recent prior working catalogue without overwriting it. New native runs are in `evidence/native-pilot-v0413/jobs`. Previous bank exports remain subject to original-ROM SHA and instruction-byte authentication.

## Implemented changes

1. **First-divergence diagnosis:** `nativecore/divergence.py` compares full authenticated external/reference streams and native candidate streams, walks past 4,096-event previews, identifies the earliest unequal event and bounded before/after context, and classifies a likely *shared subsystem* (CPU/control flow, IRQ, mapper, VDP, PSG, input). Diagnostic suggestions never change source or qualify native dispatch. With an owner-imported compatible reference, the Workbench produces `divergence-diagnosis.json` automatically on mismatch. For manual analysis:

```powershell
py -3 -m nativecore.divergence --reference 'C:\Reference\capture\reference.json' --candidate 'C:\Projects\RecompDev-v0.4.0.13\evidence\native-pilot-v0413\jobs\JOB_ID\pilot-report.json' --output 'C:\Reference\diagnosis.json'
```

2. **Concrete MAME Master System capture (experimental):** `tools/Capture-MAME-SMS.py` runs an owner-installed MAME executable from an explicitly approved local directory, after verifying the ROM SHA-256. Its included Lua script uses documented MAME Lua frame notifiers, CPU state and non-mutating Z80 I/O write taps. It saves immutable frame PC/register observations plus a separate ordered **PSG / VDP control-port write** capture. Time/frame/event limits, producer executable/script hashes and raw file hashes are recorded. Nothing is downloaded; MAME remains optional.
3. **Explicitly limited I/O comparisons:** `tools/Compare-MAME-SMS-Bus.py` compares only ordered `PSG_WRITE` and `VDP_CONTROL_WRITE` kind/address/value effects with a fully verified native event stream. VRAM/CRAM data writes, mapper, interrupts, CPU step numbers, callback PC values, controller input and video frames are **not** compared. `MATCHED_SELECTED_IO_PREFIX` is **not** CPU or gameplay parity. MAME Lua startup timing and reset alignment remain **unverified** until owner testing.
4. **Synthetic test isolation:** when the Workbench is launched with a catalogue outside its own install directory, job evidence is stored alongside that catalogue rather than polluting genuine installation jobs. This addresses the temporary `TinySMS.sms` job observed previously.
5. **Version continuity:** existing source attestation, Ghidra bank recovery, native C++ compilation, chunked event streams and adaptive step budgets remain available. Workbench labels and evidence paths are updated for v0.4.0.13.

## Running the established native pilot

Open `http://127.0.0.1:8777/execution`, choose the same prepared Master System game, leave **Adaptive replay** enabled, choose a **500,000** step ceiling, **2** recovery attempts and **1** branch-prefetch entry. Leave **Independent reference file** blank until you have an *instruction- or event-compatible independent JSON reference*; MAME frame-only data are not compatible with that full-parity field. Run the native pilot normally.

**Package the newest native job without generated C++ or ROM images (one-liner):**

```powershell
$root='C:\Projects\RecompDev-v0.4.0.13'; $job=Get-ChildItem -LiteralPath "$root\evidence\native-pilot-v0413\jobs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if(-not $job){throw 'No job found'}; $files=@(Get-ChildItem -LiteralPath $job.FullName -Force | Where-Object {$_.Name -ne 'native-project'}); if(-not $files){throw 'No evidence found'}; Compress-Archive -LiteralPath $files.FullName -DestinationPath "$env:USERPROFILE\Desktop\RecompDev-v0413-Evidence.zip" -Force
```

## Optional external MAME capture

MAME is not included. Install an appropriate, separately maintained MAME version and confirm it supports the `sms` machine and `-cart`, `-autoboot_script` and Lua frame/tap APIs. MAME's Lua API is not stable across versions. Your MAME may require machine ROM/BIOS configuration; inspect `mame-stderr.log` on failure. It must run your *original owner-local ROM*, with matching reset, region, inputs and machine model. The launcher does not assert that these conditions are matched.

**Run capture (one-liner, edit both paths):**

```powershell
$root='C:\Projects\RecompDev-v0.4.0.13'; $rom='C:\Roms\SMS\Game.sms'; $mame='C:\Tools\MAME\mame.exe'; py -3 "$root\tools\Capture-MAME-SMS.py" --mame $mame --allowed-tool-root 'C:\Tools\MAME' --rom $rom --source-sha256 (Get-FileHash -LiteralPath $rom -Algorithm SHA256).Hash.ToLowerInvariant() --output-dir "$root\evidence\independent-reference\mame-capture-001" --system sms --frames 120
```

Capture writes `frame-observations.json`, `selected-bus-reference.json`, `mame-frames.jsonl`, `mame-bus.jsonl` and process logs. **Do not enter `frame-observations.json` in the Workbench parity field.** The capture alone is not parity verification.

**Compare selected I/O effects with your newest pilot (one-liner):**

```powershell
$root='C:\Projects\RecompDev-v0.4.0.13'; $job=Get-ChildItem -LiteralPath "$root\evidence\native-pilot-v0413\jobs" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if(-not $job){throw 'No native job found'}; py -3 "$root\tools\Compare-MAME-SMS-Bus.py" --reference-dir "$root\evidence\independent-reference\mame-capture-001" --pilot-report "$($job.FullName)\pilot-report.json" --output "$($job.FullName)\selected-bus-comparison.json"
```

This may correctly return an *incomplete* result if the native run ended earlier than MAME's captured window. A mismatch may reflect different reset/inputs/timing or a Lua API mapping issue rather than incorrect generated CPU code. Do not automatically repair from an unaligned MAME capture.

## What remains blocked

- **No actual MAME owner-Windows run has been performed by the builder.** The MAME launcher is tested against a separate synthetic executable fixture; its real MAME/Lua integration remains owner-validation pending.
- No independent CPU instruction, full VDP state, whole-frame pixel, sound or gameplay parity established.
- MAME does not yet capture the full canonical event vocabulary. No external frame-to-instruction alignment; do not treat frame samples as instruction checkpoints.
- No safe autonomous shared semantic patching/rollback; the first-divergence report is an investigation input, not permission to modify sources.
- No native executable Mega Drive/M68000 or PlayStation/MIPS backend; cross-platform architecture remains an ongoing goal.

MAME Lua interfaces reviewed against the [official MAME Lua scripting documentation](https://docs.mamedev.org/luascript/) and [address-space tap documentation](https://docs.mamedev.org/luascript/ref-mem.html). Claims are deliberately narrower than the capabilities MAME may eventually allow.
