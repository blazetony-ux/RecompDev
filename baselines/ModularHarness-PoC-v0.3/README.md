# RecompDev Modular Harness PoC v0.3 — Real-ROM bridge (isolated)

## What works

This project is standalone and **does not modify RecompDev v0.4.0.45**. It extends the validated v0.2 host with:

1. A new **untranslated real-ROM probe** (`rd_game_probe`) that loads a user-provided SMS ROM, runs the existing limited Z80 interpreter and safely captures the first unsupported opcode, PC and physical ROM offset. It never claims that an unknown instruction was executed.
2. A **source-attested owner DLL generator** using the unchanged RecompDev 0.4.0.45 `nativepilot.generator.verify_export` and `emit_instruction`. A Ghidra-format P-code export for the *same ROM* is required. The owner DLL is built separately as `rd_game_owner` so the built-in synthetic regression DLL remains intact.
3. A **real-image runtime-event importer** that uses the original v0.4.0.45 `discovery/store.py` schema. It validates the ROM SHA-256, physical mapping, opcode byte, event order and optional execution report. Creates a **new** SQLite database, not the production catalogue. Observations remain unverified code candidates, not native instruction proofs.
4. A one-step Windows installer that does not require manually extracting ZIPs (distributed separately as `Install-RecompDev-ModularHarness-v0.3.ps1`).

## Important limitations

**This is not yet a playable game or an automatic complete recompilation engine.** The fallback interpreter implements only a deliberately small Z80 subset. Genuine Master System games will commonly stop at an unsupported opcode. Dynamic code, interrupts, CPU shadow registers, reset timing, and comprehensive VDP/PSG parity are not established. The native DLL generator only accepts supported, byte-attested Ghidra P-code, and may reject instructions that use unmodelled state. The runtime still reads the owner's ROM in development, so this is **not ROM-free final gameplay**. Differential `--validate` compares with this PoC's limited interpreter, **not MAME or an independent reference oracle**.

No copyrighted ROM or Ghidra export from a commercial game is bundled. The tests use original synthetic code. The release has not been tested with your specific Shinobi ROM or Ghidra export.

## After the Windows installer

Run one command from PowerShell to probe a real Master System ROM (its bytes remain in your chosen input file):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Projects\ModularHarness-PoC-v0.3\Run-RealRom-Windows.ps1 `
  -Rom 'C:\Roms\MASTERSYSTEM\Shinobi (USA, Europe).sms' -Steps 500
```

Adjust the file path to the real filename on your machine. The probe executes only implemented opcodes and creates a new `build-win\reports\rom-<sha>-<id>` directory with a `.events.jsonl`, `.report.json`, `.ppm`, `.wav` and `runtime-sidecar.sqlite`. A blocked opcode is **an expected partial-discovery result**. The ROM never gets copied into the installer or an upload.

### Compile an authenticated Ghidra-exported function set

RecompDev v0.4.0.45 includes `ghidra/ExportFunctionBodies.java`, which emits schema `recomp-function-pcode-v1`. It must be run with a Z80 language ID and a verified full-ROM SHA-256. Bank overlays require exports with explicit `bank_context`. This PoC consumes these exports **but does not run Ghidra itself**. Once you have a matching genuine export:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Projects\ModularHarness-PoC-v0.3\Run-RealRom-Windows.ps1 `
  -Rom 'C:\Roms\MASTERSYSTEM\YourGame.sms' `
  -Export 'C:\Evidence\YourGame-functions.json' `
  -BankExports @('C:\Evidence\YourGame-bank3.json') `
  -Steps 100 -Validate
```

Remove `-BankExports` if there are no bank overlays. `-Validate` is optional and only works while the limited interpreter can execute the same path. The script requires `analyzer` equal to `ghidra-raw-pcode`; source bytes and whole-ROM hash are independently checked. This field is a declared producer label, *not a cryptographic proof of Ghidra origin.*

The native module is `rd_game_owner.dll`. No game-specific changes to the main harness or synthetic test module are needed. Translated bytes match the ROM source; dynamic PC/bank identity is checked at dispatch; unmatched instructions use fallback or stop. If execution errors, any emitted observations can still be exported as a sidecar. **No production SQLite catalogue is modified.**

## Linux developer commands

```bash
cmake -S . -B build -G Ninja
cmake --build build -j
ctest --test-dir build --output-on-failure
./build/bin/RecompDevHarness --plugin-dir ./build/bin \
  --case rom --rom examples/recomp-pcode/synthetic.sms \
  --game rd_game_probe --probe --steps 20 --out build/reports/probe
python tools/import_runtime_observations.py \
  --rom examples/recomp-pcode/synthetic.sms \
  --events build/reports/probe.events.jsonl \
  --report build/reports/probe.report.json \
  --output build/reports/new-sidecar.sqlite
```

Expect **19 tests** with Python 3, including all 18 original tests. A separate executable build target `rd_game_owner` is intentionally excluded from the normal build until a specific owner game is generated. The owner DLL can be built with `cmake --build build --target rd_game_owner`.

## Promotion gates

Before adopting this into the main roadmap, require actual v0.4.0.45 Ghidra exports from at least two real ROMs, independent reference/state-timing comparisons, proper full Z80 state/interrupts, safe native/interpreter hand-off for instructions beyond the synthetic subset, runtime/code-data dependency auditing, and proof that no game-specific logic has migrated into the generic harness.
