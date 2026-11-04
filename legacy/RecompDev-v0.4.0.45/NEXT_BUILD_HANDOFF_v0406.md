# Next engineering handoff after v0.4.0.6

## Real evidence entering this release

Owner v0.4.0.5 Shinobi: 50,000 compiled native steps after one source-attested Ghidra bank-6 recovery (2 functions, 70 instructions). The last PCs alternated 0x00AC and 0x00AD. AF=37393, BC=2304, DE=65535, HL=4890, SP=57342 at the budget stop. PSG writes=11, other I/O writes=24, VRAM/CRAM writes=0. Verified CPU/gameplay parity=none. Prior bank export is anchored to v0.4.0.5 files and is not distributed.

## What v0.4.0.6 adds

- Native runner 2,000,000 step hard cap, ~25s wall-clock watchdog, checkpoint/physical-PC hotspot/port event diagnostics.
- Workbench 500,000 default budget and a new diagnostic view.
- v0.4.0.5 working SQLite catalogue prioritized, prior SHA-256 verified bank export reused only from allowlisted versioned evidence roots.
- Synthetic 296k+ instruction ADD HL/DE carry-loop compiles, executes, exits, with independently written limited Z80 opcode oracle verifying sampled registers and PC.

## Next priorities based on the owner's next report

1. Find the first real Shinobi stop after the startup delay: missing bank code, unknown CPU P-code, input/VDP status poll, halted/interrupt requirement, timing cap, or the next budget. Inspect checkpoints and physical-PC hotspots before assuming a loop is infinite.
2. Add independent Z80 CPU parity harness (registers/flags/memory mapped I/O) against a legal local reference implementation for the exact ROM hash. The synthetic subset oracle does not prove full-game parity.
3. Correct hardware timing: scanlines, frame/line IRQ scheduling, NMI/pause, VDP read buffers and control latch, controller port behaviour, RAM mapping, cart mapper edge cases.
4. Capture the first nonzero VDP control/data writes, interpret them as a verified VRAM/CRAM state transition, and only claim a rendered frame after reference image comparison.
5. Consider a bounded trace-guided real bank exploration scheduler, then genuine serializable CPU/RAM/mapper/VDP checkpoints before proposing state resume on rebuilt code.
6. Keep all new adapters generic across SMS/Z80 games, not tailored to Shinobi's hash or title.
