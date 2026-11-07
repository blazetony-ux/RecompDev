# RecompDev — PREBUILD v0.4.9.13 (owner-approved scope)

**Date:** 2026-11-07. **Approval:** owner explicitly directed "build that then please" following the detailed v0.4.9.13 Native Rizin Provider & Release Consolidation plan. **Baseline:** `workspace/v0.4.9.9` Git commit `53c42ec3b8f50f26a9dca6fbce5300fa1d9d1c63`; cumulative staged source is v0.4.9.12, which the owner validated under Windows MSVC (55/55 CTest, 38/38 Python, 642/642 histories). Neither v0.4.9.12 nor v0.4.9.13 is installed. This report records concrete implementation boundaries before changes.

## A. Failure and source inventory

Real Rizin 0.9.1 output from the owner's first v0.4.9.12 retry begins with `ESC[2K` on its own line followed by two address warnings and a valid 244-function JSON array. The 0.1.1 parser rejects the terminal erase-line sequence. The active provider imports historical `tooling.orchestrator._attempt_rizin` and `authorize_tool` from frozen sources, conflicting with the required legacy-exit roadmap. Ghidra and reconciliation/recovery still depend on frozen Python and Ghidra scripts; this build does not misrepresent their removal. The previously observed untranslated Shinobi paths, movement/scroll anomalies, graphics/audio parity and 1800-frame correctness gate remain open.

## B. Planned production implementation and exact versions

- `analysis_integration` 0.1.1 -> **0.2.0**: maintained architecture-neutral direct Rizin process provider with `rizin-provider-v1` contract, allowlisted executable and bounded subprocess execution, immutable raw log, exactly one verified `aflj` array and separate hash-bound analysis audit; no production import or call of legacy `_attempt_rizin` or legacy `authorize_tool`.
- Allow only bounded Rizin 0.9.1 terminal formatting (`ESC[2K` as standalone erase-line and SGR) plus explicitly recognized invalid-address warnings; unknown text, malformed JSON, extra records, tool errors and timeouts fail closed.
- `analysis_integration/providers.py` uses the new provider; Ghidra/export/source reconciliation paths remain unchanged and explicitly temporary.
- Test regressions for real ANSI+warning evidence, no-warning JSON, malformed/ambiguous/tool-failure outputs and cross-ISA Rizin configuration. Compiled-controller orchestration test is retained with two source-distinct synthetic ROM fixtures. No ROM-title constants in production.
- CTest registration, component registry/analysis documentation, release notes/handover and roadmap must be updated. `controller` 0.4.10, the controller's C ABI and all other compiled EXE/DLL component versions unchanged.
- Continue using **only** the permanent root `Install-RecompDev-Release.ps1` with a SHA-pinned cumulative source ZIP; no new release-specific installer. Produce an optional *offline Git checkpoint bundle* in a disposable clone as development-history preservation, without mutating live Git or claiming promotion.

## C. Acceptance and protection

Maintain the exact original 642 legacy/baseline files; never write to original commercial ROMs or owner catalogs. Bounded log size, execution timeout, process tree termination and tool/root/source hashes are mandatory. No silent historical engine fallback. Run parser/direct-provider tests, integrated native-controller synthetic tests, Python docs/tests, compile and CTest where available. Separately report Linux and user Windows results. Require owner Windows `Validate`, real Ghidra/Rizin run in fresh evidence directory, real native translation progress, second real ROM and 1800-frame semantics/parity before promotion. If any gate fails, candidate is non-promotable; Git checkpoint is **development branch only**, not a release tag. No active Git/source/binary mutation occurs in this build. A future authorized production install uses transactional rollback/backup; reject mismatched baseline, hash, or dirty tree.

## D. Explicit exclusions and forward plan

No Ghidra exporter migration, C++ analysis ABI implementation, complete Python orchestrator removal, new 68000/MIPS native translator, hardware plugin rewrite, Shinobi-specific patch or parity claim. v0.4.9.14 should extract the preserved Ghidra export and reconciliation dependencies; later releases move controller recovery scheduling from Python into compiled versioned interfaces, then enforce a disposable-tree zero-legacy runtime gate. Historic frozen code remains readable for independent differential tests only. Record exactly what was delivered and what is still blocked.
