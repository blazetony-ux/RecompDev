# v0.4.0.14 engineering handoff — stop the single-game debugging cycle

## Permanent direction

The purpose is a cross-game native recompilation pipeline, not a series of one-title workarounds. The versioned `PLATFORM_CHARTER.json` plus executable `tooling/gates.py` must stay in every release. No claim of verified native code just because static engines agreed.

## Implemented now

- Source-attested multi-tool analysis coordinator (`tooling/orchestrator.py`) with explicit owner-approved Ghidra/Rizin paths, failure quotas, byte-checked Ghidra exports and immutable provenance; independent Rizin function hypotheses are reconciled without silently accepting one engine as authoritative.
- Portable analysis format across Z80, M68000 and MIPS **synthetic raw inputs**, no ISA-specific game/title knowledge. This does not make M68000/MIPS code generation functional.
- Automatic per-job evidence-based next-action plan with no source edits, patches or automatic parity promotion.
- Read-only Workbench tool workspace and release milestone dashboard.
- Browser-disconnect write guard; MAME executable-relative ROM-root and user-defined additional BIOS search roots.
- 13 synthetic orchestration/policy tests including two independent process-run raw binaries on POSIX, plus legacy regressions.

## Next non-negotiable gate

1. Owner tests **real** installed Ghidra and Rizin against at least two independent owner-authored binaries on Windows. Record executable entrypoint SHA, outputs, and any tool syntax/version incompatibility. No single-game MAME issue should replace this gate.
2. Verify Ghidra export captures correct physical address mapping and source hashes for a real M68000 program, and Rizin agrees on at least one entry without manually modifying the analysis. Record conflicts as evidence, not guessed fixes.
3. Implement a genuinely executable second ISA backend using original author-generated fixture programs and an independent execution oracle; the optional static support now included is *not* that backend.
4. Extend work scheduling from the current static CLI into a bounded, owner-approved Workbench campaign with cancellation, parallel tool scheduling and cross-target holdout tests.
5. Build transactional shared semantic patch/rollback only after meaningful independently validated CPU and ordered bus parity contracts are demonstrated.

## Never claim

- Completed automatic conversion, generalized Ghidra/Z80 parity, MAME-verified instruction correctness, native M68000/MIPS, gameplay/native dispatch, or automatic repairs without new evidence.
- That a SHA-checked binary is automatically legally distributable or safe to execute.

## Environment limits of builder

Full Windows verification and real owner Ghidra/Rizin tool invocation have **not** been run in this build environment. Synthetic fixtures test the contracts, not upstream analyzers. Keep old releases installed for rollback. Preserve the working SQLite catalogue and local ROMs.
