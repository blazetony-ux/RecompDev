# RecompDev v0.4.0.8 — Universal Native Recompilation Framework

## The actual goal

RecompDev is a **game-independent, multi-console native recompilation workbench**. Its purpose is to convert owner-supplied, source-verified game code into native x86-64 via generated C++ and a host C++ compiler. It is NOT a Shinobi conversion project, emulator wrapper, or claim that a complete playable build can already be generated.

**Shinobi is one regression input. The features in v0.4.0.8 operate by system, CPU, ROM offset and SHA-256 — not title or game-specific fixed patches.**

## Install with Windows PowerShell

Close the previous Workbench, then run:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.8-Universal-Native-Framework.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.8\Run-Workbench.ps1'
```

Open `http://127.0.0.1:8777/execution`. The launcher creates `catalogue.v0408-working.sqlite` independently. If available, it copies the v0.4.0.7 working catalogue and retains source-verified evidence references. Keep v0.4.0.7 and v0.4.0.5 installations/evidence where they are so the worker can reauthenticate and reuse bank-6 evidence. **Original ROM bytes remain on the user's local system and are not bundled in this ZIP.**

## Changes implemented

### Shared architecture contracts

- `nativecore/registry.py` declares CPU adapters (Z80, Motorola 68000, MIPS) and console adapters (Master System, Game Gear, Mega Drive, PS-X EXE), with independent capability stages and explicit blockers.
- `nativecore/adapters.py` introduces an interface for resolving physical program addresses and recovering code, implemented by the Master System provider. Other systems do **not** silently inherit Master System semantics.
- `nativecore/recovery.py` classifies missing code at fixed vectors, initial ROM and mapped banks and enforces a bounded, duplicate-aware recovery budget.
- `systems/mastersystem/runtime.cpp/.hpp` now owns the partial console hardware implementation; `nativepilot/runtime.*` are compatibility forwarding files. Future consoles must supply their own hardware plugins.
- A Workbench capability matrix and loopback-only `/api/native-capabilities` endpoint expose honest support levels.

### Generalized native recovery

- Previously only `BANKED_CODE_NOT_TRANSLATED` initiated recovery. Now `UNTRANSLATED_INITIAL_CODE` also triggers the same source-authenticated Ghidra → C++ → compiler → replay pipeline, including Z80 `0x0038` and `0x0066` ROM vectors.
- Fixed-ROM recovery is seeded by the **observed PC**, not a hardcoded Shinobi address or handler body. The original ROM is never patched.
- The scheduler tracks `(system, region, physical offset)`, stops duplicate/repeated work, respects the configured recovery budget, and persists authenticated recovered evidence.
- Dynamic switched-bank evidence remains fully compatible; the reported recovery target includes logical PC, physical ROM offset, slot, bank and region.
- Reused evidence is restricted to this installation and trusted, adjacent version directories, and every recovered instruction is rechecked against the source ROM.

### Generic diagnostics

- Workbench accepts up to **8 configurable RAM watchpoints** as hexadecimal or decimal addresses (`0xC000–0xFFFF`). The report includes reads, writes, nonzero writes, last writer/reader PCs, and last value.
- Existing legacy `0xC001` counters remain in the runtime for backwards compatibility with historical traces and tests but are **not used by the recovery scheduler**; the UI uses configured watches.
- System-neutral capability descriptions are shown for all prepared CPU/system targets; Native Execution launches only if a valid executable backend actually exists.

### Multi-system native preparation

- The same source-hash-linked preparation catalogue registers `.sms`, header-authenticated Mega Drive images and **standalone PS-X EXE** files. MIPS target registration is now supported, but its unified Ghidra function-analysis adapter and PS1 runtime remain pending.
- The Mega Drive/68000 and PS-X EXE/MIPS CPU and console capabilities are shown with blockers. These targets **cannot** yet run through the Z80 native execution backend.
- Unsupported formats report missing adapter requirements. No incorrect cross-system native executable is generated.

## Reproducible validation

- **Two independent synthetic Master System programs** recover initially missing, source-attested `0x0038` handlers through the same pipeline. They compile with CMake/C++, run native CPU steps, execute the recovered handler, set distinct RAM flags (`0xC001` versus `0xC002`), and continue — without modifying RecompDev game logic between inputs.
- A POSIX fake Ghidra launcher verifies that the fixed-vector code-recovery command seeds logical `0x0038` at physical `0x0038`, with source-verified instruction hashes.
- Existing banked-code automatic recovery still passes its compiled test and distinguishes physical ROM offsets.
- Mega Drive and PS-X EXE synthetic files both enter the shared native preparation catalogue and cannot be misrepresented as native-execution-capable.
- Other existing discovery, catalogue, bridge, CPU/I/O and Workbench regression groups are covered by `Verify-v0408.ps1`.

## First real Windows test — Shinobi or another SMS ROM

1. Open Workbench `Native Execution`. Select an already prepared Master System game.
2. Choose a step budget of 500,000 and recovery budget of 2; optionally enter watches `0xC001,0xC002` for this particular test. For other games, watch addresses are entirely user-defined.
3. Click **Autonomously recover, compile & trace native C++**.
4. The runner should reuse the previous authenticated bank overlay, attempt to recover any missing initial-ROM code (including interrupt-vector handlers), compile, and replay from reset if new verified source instructions were found.
5. Review the recovery timeline: target region, physical offset and next stopping point. It does not guarantee a playable or visible game frame.

Evidence is recorded under:

`C:\Projects\RecompDev-v0.4.0.8\evidence\native-pilot-v0408\jobs\<job-id>\`

Please upload `pilot-report.json`, `worker.log`, `execution.log`, and the recovery `ghidra.log` if a recovery attempt fails. `diagnostic-background.png` is optional when investigating the video system.

## Known blockers and non-goals for this release

- The first real Shinobi `0x0038` recovery on Windows Ghidra has **not yet been measured**. No real Shinobi gameplay or title-screen frame is claimed.
- Z80 instruction lowering, frame timing, interrupt behaviour and Master System graphics are **not reference parity verified**.
- 68000 native execution, MIPS native execution, Game Gear hardware runtime, full original console hardware behaviour, and autonomous whole-game compilation remain incomplete. The new CPU/system adapters are capability contracts, not magic emulators or automatically complete translators.
- Verification is by synthetic and unit/integration tests; an independent emulator/reference trace for a real cartridge remains a high-priority capability gap.
- This tool is intended for games the user has the right to analyse; releases do not distribute commercial game ROMs or generated game binaries.
