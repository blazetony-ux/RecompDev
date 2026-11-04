# Next Build Handoff — after v0.4.0.12

1. Obtain genuine original-ROM **independent** Master System reset + controller + hardware event capture (e.g. independently operated emulator/trace plugin). Without compatible reference evidence, `NOT_TESTED` is the correct parity status. Do not synthesize a reference by replaying candidate logs.
2. Validate distinct event vocabulary (VDP ports, VRAM vs CRAM offsets, PSG, mapper state, IRQ delivery), Z80 flags and exact timing/input assumptions. Compare externally captured 500K-step prefix/full trace against compiled native chunks, including hardware-state hashes and checkpoint registers.
3. Use first-divergence evidence to build **shared** Z80 and Master System semantic repairs; re-run complete synthetic regression and real external holdouts. Do not patch game titles or skip mismatches.
4. Separate CPU-core and system hardware adapter contracts further, then add a second *executable* architecture, beginning with m68k, with independently tested instruction semantics. Mere Ghidra import/graph metadata is not native translation.
5. Improve multi-CPU scheduling, transactional state fallback and true frame parity only once independent reference execution exists. Any native dispatch qualification remains separately gated.

v0.4.0.12 carries forward original ROM attestation and honest stage statuses. Max 500,000 streamed events/64MiB; both records and byte cap fail closed, not silent truncation. Adaptive run always replays from reset and never exceeds the user's maximum step budget. External emulator adapter requires the owner to install/configure the executable; no emulator was bundled or automatically downloaded.
