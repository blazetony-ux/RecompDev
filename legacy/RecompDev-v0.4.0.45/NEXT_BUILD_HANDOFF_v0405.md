# RecompDev next engineering handoff after v0.4.0.5

1. **First real bank-6 analysis:** run owner's Shinobi through the v0.4.0.5 Workbench, inspect `recovery_attempts`. The previously observed target is `PC 0x8A68`, physical offset `0x18A68`, 16 KiB slot 2 bank 6. Ghidra import uses binary-loader base 0x8000 and seeds this PC. Check Ghidra's returned instruction lengths, bytes, P-code and control-flow.
2. **Reference parity:** compare translated vs reference Z80 register/flag/memory transitions on real Shinobi inputs; currently NOT_TESTED. Bank evidence hashes authenticate source bytes but not function boundaries.
3. **Ghidra memory mapping:** add 8 KiB RAM + mirror as uninitialised memory and mapper/register side effects to improve correctness of static analysis, without presenting memory as ROM.
4. **CPU edge cases:** real Z80 EI delay, IM1 NMI/IRQ scheduling, HALT, DAA parity, register aliasing and interrupt timings; dedicated tests must be added before claiming full ISA correctness.
5. **Bank trace caching and recovery:** existing v0405 local database retains a verified source/hash/slot/bank export record. Future steps might require second distinct functions in the same bank, and a more advanced deterministic scheduler.
6. **VDP/PSG:** existing basic port effects are not a functional full MS graphics/audio runtime; frame capture and deterministic reference comparison remain milestones.
7. **Checkpoint/replay:** v0405 always reboots and replays from reset on rebuild; snapshot/replay at arbitrary stops would require serialized CPU/RAM/cart RAM/mapper/VDP state plus binary-version verification.
8. **System independence:** all core pieces should stay in shared nativepilot engine, not specialized to Shinobi filename/ROM hash.

## Known regression evidence

A synthetic Master System ROM initially executes six native steps, selects cartridge bank 3 and jumps to CPU 0x8000. The orchestrator attaches a SHA-256-attested overlay for physical offset 0xC000, regenerates C++, then executes eight native steps and stops at physical 0xC005. The original cartridge hash remains unchanged. A mock external Ghidra process verified the bank-6 base/seed argument hand-off for PC 0x8A68 and 0x18A68.
