# Follow-on: independent Z80/MAME parity and complete-game code coverage

1. Capture matched initial CPU state, ROM/BIOS boot, VDP mode, mapper, interrupt timing and input sequence from the user's own MAME 0.289 setup. Legacy MAME bus writes diverge at index zero without proven equivalent startup: this is not a CPU-instruction difference.
2. Validate the new source-opcode cycle model against independently implemented Z80 test ROMs, including indexed/ED illegal and conditional instruction coverage; do not qualify unsupported paths.
3. Qualify SMS VDP scanline counter changes against a real MAME reference from the same video mode and initial frame phase. Implement proper H-counter TH-latch phase, line IRQ and sprite rendering separately.
4. Improve source-attested bank/interrupt recovery and run the exact integrated Shinobi pipeline only when it measures new data.
5. Continue holdout unseen Z80 games, and keep M68000/MIPS regressions mandatory. No game-specific address hacks or ROM-hash dispatch.
6. Honest open milestones: accurate independent CPU/VDP/PSG parity; automated verified repair; playable Shinobi.
