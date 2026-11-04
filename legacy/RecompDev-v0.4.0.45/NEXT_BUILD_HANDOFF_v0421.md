# Next engineering handoff after v0.4.0.21

Priority is **completing** the recovery/verification/host loop, not another
isolated diagnostics release or game-specific patch.

1. **Real boot-origin capture** from MAME (BIOS/cart/physical bank/PC plus
   authoritative initial register/memory state); compare with native from a
   reproducible common checkpoint. Do not compare unrelated event ordinal 0.
2. **Consume authenticated recovery queue in a real analyzer task scheduler**:
   queue exact-instruction/P-code extraction for unresolved entries, validate
   the resulting source-byte evidence, regenerate only affected native units.
   The v0421 queue is not itself executable code. Keep Rizin hypotheses distinct
   from Ghidra instruction evidence.
3. **Safe production semantics repair**: sandbox candidate source diffs,
   require independent CPU holdout and dependency-wide regression, revert on
   any mismatch. v0421 quarantined add-u32 recipe is not production patching.
4. **Connect live native Master System guest runtime to host GuestBridge ABI**:
   transfer actual VDP rendered pixels, input and PSG PCM in frame boundaries;
   independently qualify hardware state, IRQ scheduling and original frames.
   The author-created SyntheticGuest demonstrates ABI wiring only.
5. **Second ISA broadening**: branch, memory, flags and cycle tests for M68000
   with truly independent executor, not just the restricted MOVEQ/ADDQ/SUBQ/RTS
   fixture. Prove two processor backends through same campaign workflow.
6. **Milestone gating**: no native promotion or playable-game claim until
   independently authenticated parity/host functionality passes. Maintain
   immutable evidence under versioned release directories and no title-specific
   shared core rules.

Synthetic acceptance can run without commercial files. Owner Windows/Ghidra
and real original ROM remain prerequisites for real-game qualification.
