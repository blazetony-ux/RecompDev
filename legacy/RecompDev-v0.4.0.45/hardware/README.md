# RecompDev hardware runtime — v0.4.0.22

## The reusable core

- `core.hpp`: versionable CPU-neutral contracts for port and memory devices, an address-space-aware device rack, arbitrary-size BGRA32 frames, signed interleaved PCM blocks, portable headless sinks, neutral button/axis state, replayable input timelines, and rational rate clocks.
- `input_replay.hpp`: bounded versioned CSV (`RECOMP_INPUT_CYCLES_V1` followed by `cycle,port,buttons` decimal lines) for native-Z80 and other headless controllers. Timing is in guest CPU cycles; this is NOT a gameplay reference oracle.
- `runtime.hpp`: deterministic CPU-clock scheduler: clocks connected devices, delivers input at exact guest-cycle boundaries, and emits frames/audio through sinks without assuming any particular CPU or console.
- `wav.hpp`: PCM16 RIFF/WAV writer independent of the producing audio device.

These files contain no console names, game hashes, emulated CPU registers, 256x192 assumptions, system-specific clock constants, BIOS handling or platform window calls. They are provided as C++17 header-only components with no vendored third-party dependencies.

## Adapter boundaries

- `adapters/sms.hpp`: **experimental** Sega Master System Mode-4 background/tile/CRAM renderer (sprite and line-specific behaviour incomplete), latch/read-buffer/control-port modelling, three-tone-channel PSG output (noise, exact attenuation and timing incomplete), and active-low 2-button input adapter. This is **not a MAME-qualified emulation implementation**.
- `adapters/sms_machine.hpp`: SMS devices implementing the generic video/audio/input contracts.
- `adapters/alternate.hpp`: fictional system with 96x64 frame size, 2 MHz CPU clock, memory-mapped I/O, 50 Hz presentation, 16 kHz audio and a different input mapping. It is designed to catch accidental SMS-only assumptions, not to emulate a commercial console.

## Real compiled Z80 path

`systems/mastersystem/runtime.cpp` now renders its actual guest VRAM/CRAM/register state using the shared SMS tile renderer and keeps a bounded cycle-stamped PSG-write timeline. `nativepilot/main.cpp` accepts an optional cycle-stamped controller replay file (argument 8, passed through `nativepilot.engine --input-events`) and exports candidate PCM16 WAV for source-authenticated, generated Z80 execution into each adaptive attempt's evidence directory. Each WAV is hashed and labelled **approximate, not reference verified**. `nativepilot/generator.py` packages required hardware headers into each generated C++ project, so no installed global include path is necessary.

**Important limitation:** native-generated game code is still executed by the pilot, not inside the `UniversalHost` interactive window. A real guest-to-host plugin with continuous memory, timing and input dispatch remains to be implemented; this demo is not a playable game. The existing 256x192 `GuestBridge.hpp` stays for backwards compatibility, not as the new universal contract.

## Host output

- `host/UniversalHost.cpp` is an optional synthetic Win32 GDI + waveOut frontend using the same frame/audio/input types and a headless Linux smoke mode. It never loads a commercial ROM.
- `Build-Universal-Host.ps1` builds the synthetic Win32 host using owner-installed MSVC; no external downloads or bundles.
- Headless deterministic fixture tests are in `hardware/tests/device_contract.cpp` and `tests/test_hardware_runtime_v0422.py`.

## Acceptance boundaries

Synthetic cross-device determinism is demonstrated. Authentic Master System video/audio/input correctness, input-synchronised native game execution, MAME boot alignment, sprite and interrupt parity, cross-platform graphical window support, real-time mixed audio and actual game playability are **NOT ESTABLISHED**. Never describe producing a WAV or a nonblack framebuffer as native gameplay qualification.

SMS console Pause/Start is a rising-edge console NMI (vector 0x0066), **not** a controller DC/DD bit. In the host-neutral button contract, `button::Start` requests this console action; the SMS adapter queues the edge and delivers it at a guest-instruction boundary. Replay timing is specified in guest cycles. Other systems retain their own Start mapping.
