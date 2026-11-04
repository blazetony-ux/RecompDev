# RecompDev v0.4.0.22 → next engineering milestones

## Delivered, with synthetic executable evidence

- CPU-neutral, versioned C++17 hardware contracts; I/O and memory address spaces, bounded fail-closed device routing, input timelines, rational CPU/output clock ratios, arbitrary frame sizes, interleaved PCM16, generic headless consumers and portable WAV serialization.
- Two independent machine fixtures use the same infrastructure: an experimental Master System adapter and a fictional non-SMS system with different resolution, memory-mapped I/O and rates.
- Source-attested Z80 native C++ pilot now carries shared renderer/audio support inside generated projects. Candidate PPM/PNG and SHA-stamped approximate PSG WAV recorded per adaptive attempt; external controller input replay can drive native Z80 `IN` reads with guest-cycle timestamps. These outputs are **diagnostic evidence only**.
- Existing v0.4.0.21 durability, static-analysis orchestration and bank recovery retained.

## Explicit remaining acceptance gates

1. **Continuous generated-game host integration**: compile generated Z80 code as a loadable guest module and feed its actual guest frames, audio and input into the generic PC host, not only into pilot evidence exports. Authenticate owner ROM bytes at module startup; no commercial assets in release.
2. **Independent SMS hardware qualification**: establish MAME-aligned controller/read/VDP/PSG/interrupt and rendering test cases; qualify sprites, scrolling, collision and accurate sound, and replace approximate clock/IRQ behaviour.
3. **Fully generic host backends**: add tested SDL3 video/audio/gamepad implementation for Windows and Linux, with Win32 optional. The current Win32 frontend is a synthetic hardware demo only.
4. **Across real systems**: supply a second real CPU/system device implementation, not just the fictional portability fixture. Maintain no single-ROM checks in the shared hardware files.
5. **Autonomous code repair/recovery**: shared emulator-verified diagnostics must feed reversible production code regeneration, not synthetic recipe-only repair.

Do not ask the user to run the authentic Shinobi 500K pilot merely because this release built. The next authentic game acceptance needs a continuous guest-host integration or a verified hardware divergence test.
