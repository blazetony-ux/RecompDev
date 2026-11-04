# v0.4.0.30 handoff

1. Run the full Windows/MSVC regression script, verify no Windows-exclusive test failures.
2. Run the same-source comparative Sonic and Ridge Racer `benchmark-discovery` commands from README-v0430.md.
3. Inspect real `recovery-queue.json` candidates. Require decoder/independent dynamic or Ghidra/Rizin evidence before claiming resolved authentic control flow or function validity. An honest zero gain is not a release success on the authentic recovery goal.
4. Wire source-verified recovered function bodies into non-Z80 native lowering/compilation and add independent instruction semantics and CPU/hardware parity gates. The existing native Z80 pilot cannot be inferred to generalize MIPS.
5. Keep native and static evidence separate in the Workbench. Existing Shinobi v0429 campaign should be discovered under the new Native execution history section without rerunning the ROM.
6. Continue independent reference alignment, especially authentic MAME CPU/VDP/PSG timing and reset state. No game-specific patches.
