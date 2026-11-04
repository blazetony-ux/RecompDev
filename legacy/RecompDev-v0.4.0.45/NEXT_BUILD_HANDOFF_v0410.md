# RecompDev v0.4.0.10 engineering handoff

## Platform purpose

RecompDev converts games on multiple console systems to native x86-64 through shared IR/codegen/verification infrastructure. One title is not an architectural exception. The current executable pilot is Z80/Master System only, and neither native steps nor compiler success demonstrate CPU correctness.

## Completed features

1. `nativecore/dependencies.py`: ROM-attested, per-source physical-address code dependency graph; bounded unresolved branch frontier; bank-qualified identity; no raw source content persisted.
2. `nativepilot/engine.py`: bounded post-recovery branch prefetch (0–2), persistent graph summary, optional explicit reference checkpoint comparison, stop-on-missing-code behaviour.
3. `nativecore/parity.py`: strict ROM identity, explicit independent provenance, first/multiple mismatches and missing checkpoints; never generates a purported reference from candidate output.
4. Workbench `native-progress`: joins source discovery, native preparation, compiled pilot evidence and graph summaries, for each game. Discovery and Native Recompilation now show per-game progress separate from structural byte coverage and older per-function conversion tables.
5. Cross-game Z80 tests and regression checks, including migration from earlier installed catalogue. No game-name/address-specific patch was introduced.

## Next development priorities

- Actual independent reference trace ingestion (including event alignment) and CPU/VDP state comparison, not only a sampler.
- Test a **second real owner-supplied Master System game**, without changing recompilation source for its title.
- General instruction-lifting/codegen interfaces to support a 68000 native pilot and later MIPS.
- Improve code/data discrimination and indirect-branch/memory mapping confidence, and bound graph prefetch by current mapper context.
- Expose persistent aggregate *verified* function counts separately from translated and executed instruction counts.
- Keep owner ROMs local and previous versions intact; never ship game bytes in the release ZIP.
