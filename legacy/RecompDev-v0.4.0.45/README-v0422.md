# RecompDev v0.4.0.22 — Universal Hardware Device Contracts

**Architecture-focused engineering release. It is NOT a playable Shinobi game or verified emulator.** Full v0.4.0.21 source and pipelines are retained. No commercial game ROMs or BIOS are included.

## What is new and demonstrated

1. **CPU/console-independent C++17 hardware infrastructure**: logical I/O-versus-memory bus, explicit address ownership with overlap rejection, clock-based deterministic scheduler, input replay, arbitrary-size BGRA frames, PCM16 audio blocks and reusable headless sinks. See `hardware/README.md`.
2. **Two unrelated machine adapters run through the same runtime**: provisional Master System devices plus an author-created 96x64, memory-mapped fictional system at a different CPU/frame/audio rate. Synthetic tests prove exact frame/audio counts, deterministic input replay and chunk-independent playback.
3. **Native-generated Z80 video/audio evidence**: the real Z80 generator packages the shared hardware headers into each native build. Native Master System state uses the shared tile renderer; a bounded PSG port-write timeline produces a candidate WAV captured and SHA-256 labelled for each adaptive replay. A bounded neutral-button input replay (`--input-events`, `RECOMP_INPUT_CYCLES_V1`) is fed through the SMS controller adapter into compiled Z80 port reads. A source-attested author-created Z80 I/O program exercises the *real translated C++ instruction pipeline* and emits both framebuffer and WAV files.
4. **Generic host frontend**: optional Win32 GDI/waveOut synthetic graphical/audio demo built with MSVC plus a headless non-Windows smoke path. Unlike the old fixed 256x192 synthetic guest bridge, the new frame and audio contracts do not fix the display size, machine, CPU or host sample rate.
5. **Carry-forward**: SHA-authenticated Z80 recovery, persistent campaigns, analyzer handoff, M68000 restricted fixture, previous tests, Workbench and previous-version catalogues remain present. Release code hashes are verified by `Verify-v0422.ps1`.

## Explicit blockers

The Master System VDP renderer is preliminary (background tiles; no qualified sprite/collision/overflow/scroll/IRQ accuracy). The SN76489-compatible PSG prototype only has an approximate tone path, not a tested noise path, cycle-accurate mixing or reference parity. The universal interactive host currently demonstrates synthetic device output, **not an authentic generated game connected to live host input**. The pre-existing experimental emulator clock/interrupt model remains unqualified. Full Z80 semantics, MAME alignment, accurate hardware emulation, general native self-repair and a playable original game remain **unverified/incomplete**. We do not claim universal compatibility or that Shinobi is closer to playable until authentic evidence supports it.

## Installation — PowerShell one-liners

Close old Workbench. Extract into a separate version folder:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.22-Universal-Hardware-Runtime.zip" -DestinationPath 'C:\Projects' -Force
```

Launch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.22\Run-Workbench.ps1'
```

Verify source and synthetic regressions (optional):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.22\Verify-v0422.ps1'
```

Build the **synthetic** universal Win32 host from a VS Developer PowerShell (optional):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.22\Build-Universal-Host.ps1'
```

For generated native Z80 jobs, hardware outputs are evidence only: `diagnostic-background.ppm/png` and `event-streams/attempt-*/candidate-audio.wav` when the complete captured PSG history permits it. No authentic game test is required just to validate this release.

## Next meaningful milestone

1. Wire generated code, console bus, input and event scheduler into one **continuous guest runtime** that is hosted by the generic PC frontend (not the synthetic demo).
2. Independently verify individual VDP/PSG/interrupt and controller fixtures with a real MAME reference; complete the missing hardware modes.
3. Bring SDL3 or equivalent cross-platform graphics/audio/controller presentation as a separate interchangeable host backend, while keeping headless testing available.

This engineering roadmap is generic. Master System is only the first real adapter; another system must never require edits to `hardware/core.hpp` or `hardware/runtime.hpp`.
