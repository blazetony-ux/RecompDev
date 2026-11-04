# RecompDev v0.4.0.21 — Durable Conversion Integration

**Engineering release, not a playable native game.** Builds on the full
v0.4.0.20 source with an evidence-linked integration layer. No commercial ROM,
BIOS or generated owner's game project is packaged.

## What's genuinely new

1. **Durable, resumable campaigns** (`tools/Run-Resumable-Campaign.py`,
   `campaign/resume.py`). A campaign has immutable, numbered attempts. The
   controller SHA-256-authenticates the original binary, current translation
   and pipeline code, approved compiler/analyzer entrypoints, reference files,
   and stable rows from a prepared Z80 catalogue. Reopening an unchanged,
   verified attempt does not rerun compilation. Changed evidence opens a new
   attempt. Previously published reports and independent artifacts are
   validated against their manifests before reuse; tampering is a hard error.
   An interrupted attempt is not silently promoted; the controller can create
   a new attempt after owner review/clearing of a stale process lock.
2. **Analysis-to-recovery handoff** (`campaign/handoff.py`). Reconsiders
   Ghidra/Rizin hypotheses against **original analyzer exports and input bytes**,
   identifies exact physical offsets for raw mapped fixtures, and queues
   `ATTEST_EXACT_INSTRUCTIONS_AND_CONTROL_FLOW` work. This is a real normalized
   interface from analysis into recovery planning, **not** fabrication of Z80
   executable P-code, not a replacement for the existing bank-aware generator.
   External analysis tools still require explicit owner-approved paths.
3. **Reference-guided investigation** (`campaign/reference_triage.py`): imports
   source-matched MAME selected-bus comparison evidence and emits a bounded
   next-action plan. When PC/frame/step alignment is absent, the next action is
   to acquire authenticated boot/bank/checkpoint evidence. It never skips events
   until they happen to match or rewrites CPU semantics based on a raw mismatch.
4. **Compiled synthetic repair proof** (`campaign/compiled_repair.py`): after
   source-attested discovery vectors distinguish one allowable correction,
   RecompDev generates an isolated C++ implementation, compiles it with an
   explicitly selected g++/clang++, executes independent holdout vectors and
   commits **only a quarantined recipe record** if the executable passes.
   Broken candidates do not overwrite production translator/runtime code.
5. **Native guest/host ABI** (`host/GuestBridge.hpp`, `host/SyntheticGuest.cpp`):
   Win32 host can call a guest tick function to fill 256×192 BGRA framebuffer
   samples and 735 mono PCM samples and provide input bits. This bridge is
   exercised with synthetic guest logic; a generated authentic ROM runtime has
   **not** yet been connected and graphics/audio parity remains unverified.
6. **Cross-target regression and reporting**. Two different synthetic Z80 ROM
   programs compile and run through the existing Master System native pilot;
   a restricted M68000 program runs via its second-ISA path. Full job status
   and explicit blocked gates appear in the Workbench Tool Orchestration page.

## Installation — PowerShell (one-liners)

Close the old Workbench. All versions install in separate directories.

**1. Extract**

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.21-Durable-Conversion-Integration.zip" -DestinationPath 'C:\Projects' -Force
```

**2. Launch**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.21\Run-Workbench.ps1'
```

**3. Verify installation (optional)**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.21\Verify-v0421.ps1'
```

**4. Synthetic host guest/PC bridge (requires MSVC Developer PowerShell)**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.21\Build-Host-Guest-Smoke.ps1'
```

## Reusable campaign interface

For a **prepared, imported** Z80 owner binary (examples assume an existing
owner ROM, never provided with this release):

```powershell
$r='C:\Projects\RecompDev-v0.4.0.21'; $rom='C:\Roms\SMS\OWNER_ROM.sms'; py -3 "$r\tools\Run-Resumable-Campaign.py" --input $rom --isa z80 --db "$r\catalogue.v0421-working.sqlite" --rom-root 'C:\Roms' --steps 500000 --output "$r\evidence\campaign-v0421\jobs\owner-campaign"
```

Running the exact same command again reuses the verified attempt instead of
repeating native code generation. If you change the binary, preparation,
relevant engine source or approved reference evidence, a new immutable
attempt is created. `--retry-blocked` explicitly attempts a blocked campaign
again without allowing the old report to be modified.

For the restricted synthetic Motorola 68000 fixture, supply
`--isa m68k --synthetic-fixture --compiler ABSOLUTE_COMPILER_PATH`; unsupported
instructions always fail closed.

If you have a source-matched MAME bus-comparison JSON, add
`--bus-comparison ABSOLUTE_PATH`. The result is an evidence-backed
`reference-investigation.json`, *not* a native qualification.

The new stand-alone repair tool is `tools/Run-Compiled-Repair.py`. It requires
`--discovery`, `--holdout`, `--compiler` and `--output`; it accepts only the
explicitly defined **author-created add-u32** fixture format and never edits
production code. It is a proof of the repair/retest contract, not a general
solution to Shinobi or arbitrary ISA semantics.

## Acceptance and remaining blockers

See `BUILD_VALIDATION_v0421.json`, `tooling/gates_v0421.py` and
`tests/test_durable_campaign_v0421.py` for machine-tested scope.

**Not yet proven:** authentic MAME/native boot and instruction alignment,
correct Master System VDP/PSG/IRQ/frame rendering, real production semantic
repair with dependency retry/rollback, full M68000 backend, actual Shinobi
native gameplay or a standalone shippable commercial game. Genuine Windows
Ghidra/Rizin tests and native host window operation must be performed on an
owner system; no Windows success has been invented.

**Do not run another Shinobi 500K pilot merely as a release ceremony.** The
next useful authentic game test should target a defined new reference boundary
or host-integration qualification rather than reproduce the same black frame.
