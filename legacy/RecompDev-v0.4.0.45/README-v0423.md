# RecompDev v0.4.0.23 — Continuous Generated Native Host (Experimental)

The release builds on v0.4.0.22's CPU-independent hardware contracts and retains existing Workbench, discovery, Ghidra/Rizin, Z80 P-code translator, source-attested bank recovery, event capture, and restricted M68000 tools. **This is an engineering foundation, NOT a playable or verified Shinobi port. No game ROM or BIOS is distributed.**

## New working functionality

- `hardware/continuous.hpp`: bounded CPU-independent `NativeCpu`/`ContinuousSession` runner, device-time forwarding, input replay timing, host stop, step/guest-cycle/frame/walltime limits, explicit missing-code stop. No implicit emulator fallback and no platform/game-specific addresses in the core.
- **Generated native program now builds two executables from exactly the same authenticated `translated.cpp`:** `RecompDevNativePilot` (existing recovery/trace tool), and `RecompDevNativeApp` (new host). This is a second execution mode, not a separate interpreter or a game-specific source conversion.
- `nativepilot/live_sms.hpp`: transitional console-specific adapter between native Z80 guest state and the generic `Frame`/`Audio`/`Input` contracts. It renders from the **actual native guest VRAM/CRAM/VDP registers**, generates provisional PCM from the real guest's PSG write timeline, and feeds neutral controller inputs back into the guest's active-low port. Timing and video accuracy remain UNQUALIFIED.
- `hardware/win32_window.hpp`/`hardware/win32_audio.hpp`: optional host Win32 GDI window, keyboard input (arrows, Z, X, Enter), and best-effort waveOut PCM. These are detachable host presentation backends; the guest and generic loop do not depend on Win32. Their behaviour has **not** been run on the owner's Windows/MSVC installation yet.
- Headless mode records last framebuffer (`.ppm`), PCM (`.wav`), frame hashes, step/cycle counts and a bounded stop reason. `tools/Run-Continuous-Native.py` checks user ROM SHA-256 against the generation record, validates replay files and records evidence hashes. It does **not** record commercial ROM data.
- **Cross-target evidence:** two independently authored Z80 fixtures compiled into native host executables, produced deterministic frame+audio output, responded to cycle-stamped controller replay, and rejected mismatched ROMs. A fictional second machine with a different clock, video resolution and audio rate uses exactly the same `ContinuousSession`.

## What is NOT complete

- Native game correctness, Z80 semantic coverage, BIOS/cartridge alignment, automatic production repairs and authentic MAME parity are **NOT ESTABLISHED**.
- SMS VDP sprite/scroll/status/IRQ and PSG noise/timing are still preliminary; the generated app does not prove a game will render/produce correct audio.
- The first live Z80 bridge still uses the **existing SMS native guest bus** internally rather than routing all memory/port operations into the generic `Rack`. This adapter is intentionally isolated for a future fully pluggable bus conversion.
- Win32 GUI and speaker backend require owner Windows validation; Linux tests validate headless execution. No SDL or native gamepad API yet; current live controls are keyboard with deterministic replay available separately.
- Host execution is **continuous only within explicit safety limits**, not unlimited. It stops on missing translated instructions. It requires owner-local ROM bytes at runtime and is not a redistribution-ready game package.

## Installation — PowerShell one-liners

Close old Workbench; extract (preserve v0.4.0.22):

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.23-Continuous-Native-Host.zip" -DestinationPath 'C:\Projects' -Force
```

Launch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.23\Run-Workbench.ps1'
```

Optional verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.23\Verify-v0423.ps1'
```

## Using a generated native application

A successful new native pilot creates `native-project/build/Release/RecompDevNativeApp.exe` in its evidence job as well as the existing diagnostic binary. To run it headlessly, supply the owner ROM's **real** SHA-256 (from `Get-FileHash`) and the path to the generated job's `native-project`:

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.23\tools\Run-Continuous-Native.py' --project 'C:\Projects\RecompDev-v0.4.0.23\evidence\native-pilot-v0423\jobs\<JOB-ID>\native-project' --rom 'C:\Roms\<YOUR-ROM>.sms' --source-sha256 '<64-CHAR-ROM-SHA256>' --output-dir 'C:\Projects\RecompDev-v0.4.0.23\evidence\continuous-local-test' --frames 120 --steps 2000000
```

On Windows, append `--window` to enable the native window, keyboard and best-effort speaker output. To replay recorded inputs instead of a window, pass `--input-events <FILE>` using the existing `RECOMP_INPUT_CYCLES_V1` schema. These are **templates requiring the user's actual paths**; no Shinobi-specific command is embedded.

At the end inspect `continuous-session.json`, `native-frame.ppm`, and `native-frame.wav`. `FRAME_BUDGET_REACHED` means the requested guest-frame budget was reached, **not** that a game is complete or its frames are correct. A `UNTRANSLATED_*`, `BANKED_*` or similar block remains a code recovery task.

## Next engineering gates

1. Use the same bus implementation for native guest and generic `Rack`, with independently tested byte-accurate I/O and memory callbacks. Avoid duplicated hardware state.
2. Qualify instruction semantics and cycle/IRQ behaviour against an independent Z80 reference on two authentic targets.
3. Validate Win32 window, speaker, input and the generated app from an actual Windows pilot, then refine the host API for SDL, physical gamepads, multi-system audio and host frame pacing.
4. Integrate verified analyzer discoveries into native code regeneration and implement fail-closed autonomous recovery; use a milestone Shinobi run **only when** these changes make it meaningfully diagnostic.
