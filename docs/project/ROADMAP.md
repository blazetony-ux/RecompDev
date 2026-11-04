# Current roadmap and acceptance gates

**Status:** Current. Last reviewed: 2026-11-04.

## Completed and demonstrated

1. Historical-source preservation gate: 581 v0.4.0.45 files and 61 harness v0.3 files verified unchanged.
2. Compiled controller capable of invoking preserved Python discovery, preparation and continuous native recovery.
3. Owner-reported Shinobi session advanced to 120 frames after three bounded recovery rounds; **gameplay parity not established**.
4. Permanent v0.4.4 Git workspace with independently versioned and deployed harness DLLs, external output directories and Windows tests.
5. v0.4.5 adds documentation governance; no new CPU or hardware functionality.

## Next engineering milestone: production plugin integration

Demonstrate that changing an independently built Z80 CPU, translator or Master System plugin affects **real production instruction processing** via a documented, versioned contract, without rebuilding the controller or altering the preserved legacy source. Retain validated fallback, record plugin identity/hash in per-run evidence and prove a rollback. No synthetic-only substitution is sufficient.

## Later work, not yet validated

- Hardware-state capture at source (selected-frame raw VRAM, CRAM, VDP register and timestamped PSG traces).
- Independently aligned video/audio/interrupt parity on Master System ROMs beyond the synthetic harness.
- Correct silence diagnosis, asset extraction and eventual ROM-independent generated game executable.
- Proper CPU/translator and machine plugins for Motorola 68000/Mega Drive and MIPS R3000A/PS1.

## Cross-game acceptance

Avoid progress measured only in Shinobi instruction counts. Validate at least two additional Master System titles with source-attested behavior, and report failures as carefully as successes. Use the shared controller and plugin APIs rather than per-game branches.

## Phase-1 outcome, workspace v0.4.6

Versioned CPU DLL admission of authentic Z80 bytes is now wired into the real recovery hand-off; it is source validation only. Next, migrate the native instruction translation/execution interface so a swapped component changes emitted native C++ behaviour and hardware correctness can be validated independently. Machine/VDP/PSG plugin adoption remains pending. Continue using small, reversible Git patches and never modify frozen legacy baselines.
