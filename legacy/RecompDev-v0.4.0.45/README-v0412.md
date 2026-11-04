# RecompDev v0.4.0.12 — Progress-Aware Execution and Full Event Streams

**Goal:** reusable source-attested native recompilation infrastructure, not a Shinobi/Sonic-specific converter. The current *executable* conversion path remains experimental **Z80/Master System** only. Native Motorola 68000, MIPS and verified gameplay are not yet implemented.

## Installation — PowerShell (one-liners)

Close the old Workbench. Download the v0.4.0.12 ZIP into Downloads.

**1. Extract**

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.12-Progress-Aware-Oracle-Evidence.zip" -DestinationPath 'C:\Projects' -Force
```

**2. Launch**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.12\Run-Workbench.ps1'
```

The new `catalogue.v0412-working.sqlite` copies the prior working v0.4.0.11 catalogue on first launch, without modifying it. Previous native bank exports are treated as cached evidence **only after original ROM and instruction-byte verification**. The original game ROMs stay local; no commercial ROM is included.

## What's new

1. **Lossless ordered candidate hardware events within bounded limits.** The native runtime streams JSONL chunks of 1,024 events each to `evidence/native-pilot-v0412/jobs/JOB/event-streams/attempt-AA-budget-B/hardware-events-NNNNNN.jsonl`, with a SHA-256 manifest. The inline 4,096-event `pilot-report.json` array remains an explicitly truncated *preview*. A complete stream is limited to 500,000 events / 64 MiB; I/O or capacity failure halts with an explicit failure rather than reporting complete evidence.
2. **Full-stream independent comparison.** `recomp-independent-stream-reference-v1` compares a genuinely external hardware event stream against the full source-attested native stream. Chunk hashes, counts, ordering and boundaries must match manifest. The first differences are reported (event index, kind, address, value, PC, optional step), not hidden by an automatic resynchronizer. Optional sampled CPU-state and final hardware-state hashes remain supported. Older sampled checkpoint and 4,096-event prefix formats are retained.
3. **Adaptive step budgets, opt-in in Workbench.** Select a step ceiling, keep **Adaptive replay** checked and the runner starts with 50,000 steps, replaying from reset at 100K, 200K, 400K, etc. only when sampled PC/register/mapper/observable memory/device state changes. It never exceeds the selected maximum; it cannot prove a loop is productive or safe, and never extends on wall-clock exhaustion, missing code, hardware trace failure or a non-progressing run. Separate budget-specific logs and full event chunks are retained.
4. **External emulator adapter protocol.** `tools/Run-External-Oracle.py` optionally starts an **owner-chosen** locally installed reference emulator through a fixed argv template after independently verifying the input ROM SHA and the emulator's approved installation root. It imports its actual JSONL capture as a SHA-attested reference, records tool and configuration hashes, and never runs a shell. There is **no** integrated or bundled real Master System reference emulator. A matching independent emulator, trace plugin and configuration must actually be provided; a successful import is not proof of emulator correctness or independence.
5. **Workbench and installer continuity.** New v0.4.0.12 owner-local evidence and catalogue paths, previous-version reuse, existing Ghidra recovery, compile, dependency graph and diagnostics stay intact.

## Next Windows pilot

Visit `http://127.0.0.1:8777/execution`, choose the same prepared Master System game, leave **Adaptive replay** enabled, select **500,000** as the step ceiling, recovery attempts 2, prefetch 1. Do not enter an independent reference file until one has genuinely been captured. Click **Autonomously recover, compile & trace native C++**. A pilot should produce event-stream chunks even when the report's inline events are truncated. In the Workbench the result will distinguish full candidate event capture from actual independent parity.

**Pack latest job evidence (one-liner, excluding native-project and any ROM):**

```powershell
$jobs='C:\Projects\RecompDev-v0.4.0.12\evidence\native-pilot-v0412\jobs'; $job=Get-ChildItem -LiteralPath $jobs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if(-not $job){throw 'No native job found'}; $files=@(Get-ChildItem -LiteralPath $job.FullName -Force | Where-Object { $_.Name -ne 'native-project' }); if(-not $files){throw 'No evidence files found'}; Compress-Archive -LiteralPath $files.FullName -DestinationPath "$env:USERPROFILE\Desktop\RecompDev-v0412-Evidence.zip" -Force
```

## Connecting a real reference emulator

**This section is optional.** Do not claim parity without a separate original-ROM emulator running the same ROM, reset state, controls and event semantics.

- Supply a JSONL-capable external emulator that emits lines such as `{"type":"event","step":12,"pc":205,"kind":"VDP_CONTROL_WRITE","address":191,"value":128}` (or compatible `checkpoint` lines).
- `examples/oracles/reference-adapter.example.json` is an **interface example**, not executable emulator configuration. Change the executable and arguments to the *actual* emulator's documented CLI; it must be under an owner-approved tool root.
- The reference adapter requires explicit permission via its CLI command. Example **template** (replace paths and hash with actual values):

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.12\tools\Run-External-Oracle.py' --adapter 'C:\Reference\adapter.json' --allowed-tool-root 'C:\Tools\IndependentEmulator' --rom 'C:\Roms\SMS\Game.sms' --source-sha256 '<64-character-real-SHA256>' --output-dir 'C:\Projects\RecompDev-v0.4.0.12\evidence\independent-reference\capture1' --steps 500000
```

For an existing externally captured JSONL file, import directly into an **empty** capture folder:

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.12\tools\Import-Independent-Trace.py' --input 'C:\Reference\external-events.jsonl' --source-sha256 '<64-character-real-SHA256>' --producer 'Independent emulator name/version/settings' --stream --output 'C:\Projects\RecompDev-v0.4.0.12\evidence\independent-reference\capture1\reference.json'
```

The last command requires `capture1` to already exist and not contain event chunks. The external adapter creates its new output directory itself, so do **not** precreate it for the adapter. If using an imported capture in Workbench, enter `capture1/reference.json` in **Independent reference file**. Provenance labels and executable hashes establish the *declared origin and integrity*, not that another emulator really behaves independently of RecompDev.

A command-line comparison of a new native report against an existing independent capture can use:

```powershell
cd 'C:\Projects\RecompDev-v0.4.0.12'; py -3 -m nativecore.parity --reference '.\evidence\independent-reference\capture1\reference.json' --candidate '.\evidence\native-pilot-v0412\jobs\YOUR_JOB_ID\pilot-report.json'
```

`--complete` during external import is appropriate **only if** the external trace is the full event stream for the exact matching bounded execution. By default, imported references are explicitly marked as **prefix only**.

## Testing / limitations

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.12\Verify-v0412.ps1'
```

Source tests run in Linux with `g++`, CMake and Python; no owner Windows/Ghidra run or genuine independent emulator was available during building. No game-title-specific exception was added to the shared converter. This release does not repair gameplay, prove CPU/VDP timing parity, render a playable frame, or add a functional 68000/MIPS backend. No ROM files or private game binaries ship with the release.
