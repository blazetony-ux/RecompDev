# RecompDev v0.4.0.4 — Native Execution Pilot

This is a full independent RecompDev installation, preserving prior v0.4.0.3
and its catalogue. It is **not** a playable Shinobi conversion. It adds an
actual owner-local **static Z80 P-code-to-C++ compilation and trace path**.

## Install / run from PowerShell

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.4-Shinobi-Native-Pilot.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.4\Run-Workbench.ps1'
```

Close the old Workbench before starting the new one (local port 8777).
Open `http://127.0.0.1:8777/execution` and select Shinobi, then press
**Generate, compile & trace native C++**.

The release automatically snapshots an existing working catalogue, prioritising
v0.4.0.3 with prepared native targets. The Ghidra `functions.json` export is
*not* included in this ZIP because it is game-specific owner evidence. The
existing v0.4.0.3 export must remain where the previous preparation report
recorded it. If that evidence has been moved, run **Prepare for Native
Recompilation** again from the Autonomous Discovery page.

## What's genuinely new

- Static translator for the principal P-code opcodes in the real Shinobi export,
  producing explicit C++ statements, not a CPU instruction decoder or an
  emulator fallback. It also authenticates every instruction's bytes against
  the original owner's ROM and rejects conflicts and suspicious 0xFF padding.
- Sega-style cartridge bank mapping with a fixed first 1 KiB, three switchable
  16 KiB windows, mapper side effects on mirrored RAM, cartridge RAM, and 8 KiB
  work RAM plus mirror. Untranslated bank code fails closed.
- Basic VDP register/control/data-port effects, VRAM/CRAM, controller reads,
  PSG write accounting, and optional **background-only** PPM/PNG diagnostic.
  Sprite rendering, video timing, interrupt scheduling and actual PSG audio
  synthesis are not yet implemented.
- Bounded generated CMake/MSVC or CMake/GCC executable and runtime trace,
  with exact native step count, memory writes, I/O counts, bank changes and
  first stop reason. CMake and an available C++17 compiler are required on the
  user's machine.
- Native Execution Workbench page with launch, cancellation, job log, new
  persistent SQLite report records, and generated diagnostic preview.
- Source provenance, sandboxed ROM-folder selection, local-origin action
  token, argv-based worker processes and preserved original source bytes.

## Status language matters

- `translated_instructions`: Ghidra instruction records for which the generator
  emitted C++ source, **not** fully verified functions or unique code coverage.
- `native_steps`: actual instruction switch cases executed by the compiled
  executable in this particular bounded trace, **not** translated code count.
- `UNTRANSLATED_OR_UNREACHABLE_PC`: code reached an address absent from the
  verified P-code export.
- `BANKED_CODE_NOT_TRANSLATED`: the active cartridge bank changes the physical
  code mapped at the logical PC and no matching bank-specific compiled routine
  exists.
- `HALT_REQUIRES_INTERRUPT_SCHEDULER`: the game waits for hardware interrupt
  events not yet supported by the runtime.
- `NATIVE_STEP_BUDGET_REACHED`: the bounded test hit its cap; this says
  nothing about gameplay or correctness.
- `PILOT_BLOCKED`: missing export, hash change, unavailable compiler or another
  explicit prerequisite.

Ghidra's decimal-adjust (`DAA`) instruction has a complex instruction-local
P-code flow; v0.4.0.4 **intentionally rejects** those four Shinobi records
rather than generating incorrect native semantics. The original export has
2,130 instruction *records*. 2,126 were lowering-compatible in the
isolated source-level check (some candidates can be rejected at generation due
to padding/overlap). **None are yet proven cycle accurate, fully function
verified or game-reference equivalent.**

The output C++ reads the original ROM *locally at execution time* as data for
memory, DMA/VRAM and cartridge access. It does not interpret or emulate Z80
instructions and it does not contain a complete binary copy of the ROM.
This is still a research pilot and cannot guarantee Shinobi boots or draws a
correct frame.

## Evidence / test instructions

Each attempt writes under
`evidence/native-pilot-v0404/jobs/<job_id>/`:
`pilot-report.json`, `native-project/` with CMake project, optional
`compiler.log`, `execution.log`, `diagnostic-background.ppm` and
`diagnostic-background.png`. The original ROM is never served by Workbench.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.4\Verify-v0404.ps1'
```

The container tested generated C++ on Linux using a synthetic header-valid
Master System ROM, and syntactically compiled a translation of all available
Shinobi instruction records. Real Shinobi execution and Windows CMake/MSVC
compilation are **not yet tested**; the first owner's native-pilot run is
necessary to measure how far it actually executes.

## Next blockers

Accurate instruction-local DAA lowering, replayable reference traces, correct
interrupt and frame scheduling, full VDP sprites/audio, all ROM banks with
physical code identities, RAM-executed code, and whole-game parity. These are
not hidden by the diagnostic hardware compatibility layer.
