# RecompDev v0.4.0.11 — Independent Event Trace Verification

RecompDev remains a **game-independent native recompilation platform**. This release adds ordered hardware-effect diagnostics and a reusable *external* trace ingestion/comparison protocol. It is **not** proof of Shinobi parity, complete Z80 correctness, playable game output or a 68000/MIPS execution backend.

## Windows installation

Extract `RecompDev-v0.4.0.11-Independent-Event-Traces.zip` into `C:\Projects` without overwriting previous installations. Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.11\Run-Workbench.ps1'
```

The launcher creates a **separate** `catalogue.v0411-working.sqlite` based first on the previous v0.4.0.10 working catalogue. Prior ROMs and bank exports stay owner-local. The program re-verifies original ROM and each recovered instruction's SHA before generation. Existing previous install evidence is never modified. Python 3, CMake, native C++ compiler and a locally configured Ghidra are required for real recovery/builds.

## New architecture

- In the shared Z80 native runtime, bounded **ordered** events include mapper changes, VDP control/data and status reads, VRAM/CRAM writes, PSG writes, controller reads, IRQ and NMI. Each event carries original executing logical PC, native instruction index, type, address and value. `events_total` and `events_truncated` prevent a 4,096-record buffer from looking complete. In the pilot-report, the native event trace is explicitly candidate evidence.
- The native runner hashes its final local `hardware-state-vram.bin`, `hardware-state-cram.bin` and `hardware-state-vdp-registers.bin`, exposing only SHA-256 values in the report for independent state comparison.
- `nativecore/parity.py` supports both existing `recomp-independent-checkpoint-reference-v1` and new `recomp-independent-event-trace-v1`. Ordered event `ordinal` alignment compares effects without insisting emulator step counts agree; `step` alignment requires equality of native and reference instruction indices too. **Neither mode silently skips, reorders or realigns missing events.** An optional CPU checkpoint list and final VDP-region digests offer extra checks.
- Divergence, incomplete native coverage and matched sampled event prefix are distinct results; mismatches block parity claims. Source hashes must agree. Provenance strings identify who claims independence but cannot certify it.
- Works with the existing system-independent graph and bounded recover-compile-run pipeline. No hardcoded game, bank, ROM or hardware-address exceptions were introduced into the common engine.

## Capture a real independent trace

Capture one event per line from an *independently operated* legal reference Z80/Master System implementation or external instrumentation. Export JSONL (UTF-8) with numeric fields. Example records:

```jsonl
{"type":"event","step":12,"pc":256,"kind":"VDP_CONTROL_WRITE","address":191,"value":32}
{"type":"event","step":14,"pc":260,"kind":"VDP_CONTROL_WRITE","address":191,"value":129}
{"type":"checkpoint","step":1000,"pc":321,"af":128,"sp":57342}
```

Use the same event vocabulary and address semantics as `systems/mastersystem/runtime.cpp`: `VDP_CONTROL_WRITE` records the low 8-bit port; `VRAM_WRITE` / `CRAM_WRITE` records destination VRAM/CRAM offset, and `MAPPER_WRITE` the CPU mapper register address. Event order and values must be authentic from the external engine, not copied from generated output. Do not submit the native candidate report as a reference.

```powershell
cd C:\Projects\RecompDev-v0.4.0.11
mkdir evidence\independent-reference -ErrorAction SilentlyContinue
$sha = 'PUT_THE_64_CHARACTER_ROM_SHA256_HERE'
py -3 tools\Import-Independent-Trace.py --input 'C:\ReferenceTraces\capture.jsonl' --source-sha256 $sha --producer 'Independent Z80 reference / version / setup' --alignment ordinal --output evidence\independent-reference\my-external-capture.json
```

Omit `--complete` to compare just an authentic prefix; add `--complete` only when the reference covers the **entire** event stream of the *same bounded execution*. The tool records the external raw trace SHA-256. It does **not** generate an emulator trace or establish independence itself. To compare directly to an existing local report:

```powershell
py -3 -m nativecore.parity --reference evidence\independent-reference\my-external-capture.json --candidate evidence\native-pilot-v0411\jobs\<JOB_ID>\pilot-report.json
```

Or select `my-external-capture.json` in the Workbench Native Execution page before starting a pilot. Compare only runs with compatible reset state, input, mapper state and controller behaviour; mismatches at different input or timing conditions are not automatically equivalent. Keep actual original ROMs and raw reference files local.

## Testing

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Verify-v0411.ps1
```

The release source has deterministic positive and negative event-verification tests, a JSONL importer test, and executable C++ synthetic mapper/VDP/IRQ tests. Linux container tests here cannot reproduce owner Windows/Ghidra environments. Latest formal validation details are in `BUILD_VALIDATION_v0411.json`.

## Known blockers

The current executable native path is **Z80/Master System experimental only**. Video, PSG, IRQ timing, instruction semantics, and frame rendering are not independently proven. Real commercial Master System game parity is **NOT_TESTED** in the available evidence. Mega Drive m68k and PSX MIPS executable backends do **not** exist yet. External tracing is user-operated and requires a reference implementation plus compatible captures; this release does not execute an independent emulator automatically. Distinct translated/compiled/observed counts are not verified full-function or gameplay counts.

To investigate a Windows run, archive the new native job folder **excluding** `native-project` and any ROMs, and include `pilot-report.json`, `execution.log`, `worker.log`, and `parity-report.json` when present.
