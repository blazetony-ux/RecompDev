# RecompDev v0.4.0.5 — Autonomous Native Recovery

## What this release really does

Continues the v0.4.0.4 *compiled Z80 native execution* pilot with a **bounded bank-aware recover → rebuild → replay loop**. When the owner's Master System program executes into an untranslated physical ROM bank, RecompDev can:

1. Capture the source's mapped CPU PC, mapper register state, physical ROM offset, last CPU PCs, and register state.
2. Extract only the relevant 16 KiB ROM window to a **temporary** owner-local file for Ghidra headless analysis (deleting that temporary file after analysis).
3. Seed Ghidra at the actual stopping PC, export recovered Z80 P-code, and verify every exported instruction's SHA-256 against the original source at the **physical offset**.
4. Generate bank-qualified native C++ using a physical-ROM-offset dispatch key, compile using the local CMake/C++ toolchain, replay from reset, and stop cleanly when it encounters further missing code.
5. Repeat at most the configured number of recoveries (default 2; maximum 5). Persist recovered bank evidence in the copied working SQLite catalogue for later runs and reattest reused exports.

Original ROM data are not shipped, uploaded to Workbench, or modified. New generated exports contain instruction hashes/P-code, **not** a distributable ROM image. No Z80 interpreter fallback is used.

## New Workbench flow

Open `http://127.0.0.1:8777/execution` after launching Workbench. Select your prepared Shinobi ROM and choose a **Recovery attempts** budget. Click **Autonomously recover, compile & trace native C++**. The Workbench shows the log, the first or final native trace, and a per-attempt timeline. Full diagnostics are under `evidence/native-pilot-v0405/jobs/<job-id>/`.

Expected first recovery request based on the owner's v0.4.0.4 trace: `PC=0x8A68` with mapper `[0,0,1,6]`, corresponding to physical ROM offset `0x18A68`. Whether the real Ghidra run recovers enough code to advance Shinobi **has not been measured on Windows**.

## Install with PowerShell

Extract the full ZIP to `C:\Projects` (old RecompDev directories remain intact):

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.5-Autonomous-Native-Recovery.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.5\Run-Workbench.ps1'
```

Close other Workbench versions using local port 8777 first. The launcher creates a new `catalogue.v0405-working.sqlite` by SQLite snapshot, prioritising `v0.4.0.4` and preserving existing Shinobi preparation data (the original DB remains unchanged).

## Scope and caveats

- This is **not** a playable Shinobi conversion. No correct Master System frame timing, sprite renderer, full PSG sound output, interrupt scheduling, or independently verified original-vs-native CPU parity is established.
- Z80 DAA now lowers via a dedicated native routine, but the hardware/CPU parity tests remain incomplete. `EI` interrupt latency and some Z80 semantic edge cases remain unmodelled.
- The seed reset JP is checked against real source bytes but is not yet independently tested against a reference execution trace. Ghidra candidate boundaries remain provisional.
- Only the stopping ROM window is analysed. Recovery budgets are deliberately bounded, not unbounded whole-cartridge Ghidra sweeps.
- Generated C++ is based on Ghidra P-code, with strict stop-on-missing-instructions. Source hashes establish provenance, **not** behavioural correctness.
- Compiling bank-specific Ghidra exports was validated with a fake Ghidra launcher and a synthetic cartridge. The real Ghidra 12.2 bank-export workflow **must be exercised on the owner's Windows installation**. If Ghidra fails, the full failure log and `BANK_*` status are preserved.
- Auto-recovery restarts the game from reset rather than checkpointing at the failure. Checkpoint/replay correctness, frame rendering and parity remain future work.

## Where to look when Shinobi stops

Upload the latest `pilot-report.json`, `worker.log`, `compiler.log` if the build fails, and the relevant `recovery/attempt-*/ghidra.log` if Ghidra fails. The `recovery_attempts` list in the report gives the real native step count and physical offsets by attempt.

## Verification

The release contains regression tests under `tests/`, a SHA-256 manifest `FILE_SHA256_v0405.json`, a validation summary `BUILD_VALIDATION_v0405.json`, and optional Windows test runner `Verify-v0405.ps1`. Synthetic compiled C++ tests prove execution across a bank switch; they are not substitutes for a real Shinobi run.
