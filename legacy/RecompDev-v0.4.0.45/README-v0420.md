# RecompDev v0.4.0.20 — Consolidated Native Conversion Foundations

**Release class: integrated engineering preview, NOT a completed native-port milestone.**

This build consolidates the engineering work proposed for v0.4.0.15 through
v0.4.0.20 in a single source release without asking the owner to run six
intermediate Shinobi pilots. It is deliberately honest about which gates remain
blocked. This is not a Shinobi fix, nor a production-compatible M68000 recompiler.

## Implemented in this build

- **One campaign interface**, `tools/Run-Campaign.py`: SHA-attested raw input, bounded
  optional external Ghidra/Rizin analysis, native translation/compile/execution
  stage, optional explicit reference alignment, optional hardware sample
  comparison, per-stage immutable report and explicit remaining blockers.
  The Master System/Z80 path calls the existing recovered-code native pilot
  when a prepared catalogue and owner-approved source root are available.
- **Authenticated execution anchors** (`nativecore/alignment.py`): explicit
  code origin, bank, physical offset, logical PC, original instruction bytes,
  ISA and register samples. Matching PC alone is rejected. No heuristic skipping
  ahead in MAME traces. Byte checking is SHA-bound to the owner's raw source.
  **This does not yet extract authenticated BIOS/cartridge mapping from MAME.**
- **Hardware comparison contract** (`nativecore/hardware_gate.py`) for VRAM,
  CRAM, VDP registers, RAM and PCM digests. Rejects comparisons lacking
  authenticated aligned hardware boundaries. Native qualification always false.
- **Quarantined synthetic semantic recipe exploration** (`campaign/repair.py`):
  candidate operations tested against discovery and separate holdout vectors,
  mismatches rejected and published as evidence without changing production
  translator/runtime sources. This is NOT live automatic semantic repair.
- **Native host demonstration** (`host/StandaloneHost.cpp`): an optional
  Windows Win32/GDI 256x192 window with keyboard state and a WinMM PCM output
  hook. Uses an original synthetic test pattern and silence. Compiles on Linux
  in explicit headless smoke mode. **It is not wired to gameplay.**
- **Restricted M68000 static C++ lowering** (`nativecore/m68k_fixture.py`):
  original test programs only; MOVEQ, ADDQ.L, SUBQ.L and RTS, with compiled
  register outcomes checked against separately implemented Python test oracle.
  Flags, memory, branches, exceptions, interrupts, peripherals and all other
  opcodes are BLOCKED. An original game is not supported by this backend.
- **Architecture milestone gate** (`tools/Validate-Milestones.py`) checks both
  legacy architecture requirements and the new integrated synthetic cases.
  Read `BUILD_VALIDATION_v0420.json` for the exact validation scope.

## Critical limitations still open

1. Real Ghidra/Rizin tool invocations have not been tested on the owner's
   Windows machine. Findings are *hypotheses* until verified and wired to a
   complete generator; the unified adapter does not silently treat them as
   executable guest semantics.
2. The existing Master System native runtime has no proven MAME instruction,
   cycle, frame, mapper or hardware parity and is not a playable game.
3. MAME and native trace capture still need a **common authenticated reset / ROM
   mapping / checkpoint protocol** for true instruction-level differential replay.
4. The quarantined semantic recipe harness does not modify or retry live CPU
   backend source; a production transactional patch pipeline remains blocked.
5. Win32 frontend isn't connected to the generated Master System game and
   hasn't been compiled/tested on the owner Windows environment.
6. The M68000 backend is a small author-fixture compilation path, **not** an
   arbitrary-game translator. No second ISA has production hardware parity.

## Installation — PowerShell (two one-liners)

Close the old Workbench.

**1. Extract:**

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.20-Consolidated-Native-Foundations.zip" -DestinationPath 'C:\Projects' -Force
```

**2. Launch:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.20\Run-Workbench.ps1'
```

The new working database is `catalogue.v0420-working.sqlite`, seeded with a
SQLite backup of the previous valid catalogue; old installations are unchanged.
The Workbench is at `http://127.0.0.1:8777/` and tooling status at `/tooling`.

**Optional one-liner — verification:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.20\Verify-v0420.ps1'
```

**Optional one-liner — independent synthetic M68000 compilation smoke:**

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.20\tools\Run-Milestone-SelfTest.py'
```

Requires CMake and an installed C++ toolchain, or an approved C++ compiler on
PATH. A smoke PASS is not game parity.

## Unified campaign CLI (explicit opt-in only)

For a **previously prepared and registered** Master System title, the existing
SQLite catalogue must map the SHA256 source ID to a source file under a
configured owner source root. The example shows the interface; running it
uses a real owner-local ROM and intentionally writes evidence only to the new
release directory:

```powershell
$r='C:\Projects\RecompDev-v0.4.0.20'; $rom='C:\Roms\SMS\OWNER_ROM.sms'; py -3 "$r\tools\Run-Campaign.py" --input $rom --isa z80 --db "$r\catalogue.v0420-working.sqlite" --rom-root 'C:\Roms' --steps 500000 --output "$r\evidence\campaign-v0420\jobs\pilot-$(Get-Date -Format yyyyMMdd-HHmmss)"
```

Only execute after replacing `OWNER_ROM.sms` with your existing legal owner
file. This is **not required for this release's acceptance**; no repetitive
Shinobi test is requested.

Optional third-party analyzers require `--rizin`, `--ghidra`, and
`--allow-tool-root` arguments, with exact explicitly approved tool executable
paths. None are installed or downloaded. Invocation is sandboxed by source,
output, timeout and size limits, but third-party executables remain software
that the owner must trust.

## Source and privacy

No commercial game ROM or reference emulator is packaged. Synthetic CPU bytes
in tests are author-created. Original binaries remain owner-local and are
SHA-verified before/after work. A release ZIP is not a legally distributable
native game. Don't ship commercial game assets without permission.

**Optional one-liner — build the synthetic Windows host (not a converted game):**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.20\Build-Host-Demo.ps1'
```

Other new CLI entrypoints: `tools/Compare-Execution-Anchors.py` validates a
caller-provided exact anchor pair; `tools/Trial-Semantic-Repair.py` searches a
bounded list of author-known `add-u32` semantic recipes against independent
source-hash-preserved holdouts. Neither performs automatic production changes.
