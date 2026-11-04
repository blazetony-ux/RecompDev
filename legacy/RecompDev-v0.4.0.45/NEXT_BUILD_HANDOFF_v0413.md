# v0.4.0.13 engineering handoff

The essential next gate is owner-run, original-ROM MAME/Linux or Windows external verification. In this build the concrete independent MAME frame + selected PSG/VDP-control port capture is new and **untested with a genuine MAME binary**. Require exact ROM SHA, machine/region/reset/input parity and MAME API compatibility before interpreting any mismatches as implementation faults.

Suggested next engineering increments:

1. Run MAME Lua capture on the same owner ROM and compare the selected I/O effects against the existing 500K step pilot. Recover or correct any MAME API quirks in shared adapters, never title-specific code. Explicitly establish reset alignment; current selected-bus comparison does not establish it.
2. Extend canonical reference capture to VDP data port / internal VRAM and CRAM state, IRQ handling and CPU instruction checkpoints **without synthesizing missing fields**. Ensure ordering and cycle/step semantics are independently established. No full parity status until matching scopes are measured.
3. Use SHA-attested first-divergence reports to prioritise shared semantics. Repair source only in an approved sandbox, with independently generated tests, cross-game holdouts and automatic rollback. Avoid automatic blind rewrites.
4. Introduce an actually executable m68k backend using author-written test binaries plus an independent CPU oracle, not a Sonic-only workaround. MIPS follows real instruction tests.
5. Continue separating multi-CPU runtime, hardware scheduling, portable native dispatch and conversion adapters while preserving original ROM provenance.

Regression tests must be rerun on Windows. No downloaded MAME, Ghidra, real game ROM or authentic trace is shipped. Evidence for currently running games remains `NOT_TESTED` for full independent parity.
