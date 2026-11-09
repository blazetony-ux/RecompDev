## Generated-source preservation (v0.4.9.28 candidate)

The CPU-neutral `generated_source_sync.py` manages a private, Git-backed generated-source remote independently of the RecompDev controller repository. Original local `gs/<rom SHA256>` Git commits are immutable provenance; unsquashed subtrees map those histories beneath `generated/roms/<sha>` on one remote `main` branch, and `generated/provenance/<sha>.json` points to the original source commit/tree for exact restoration. The system refuses dirty, divergent, symlinked, unexpected or binary source files. Verified activation receives immediate local Git commits and queues asynchronous remote backup; a failed push leaves a durable pending marker for a later retry, never blocks gameplay.

The owner must configure an existing private shared clone or allow the installer to detect a sibling `RecompDev-plugins`. `setup`, `status`, `publish`, `restore-all` provide diagnostic entrypoints. The installed release restores per-ROM Git history from the remote before relying on the saved generated source to rebuild compatible native DLLs; no binary DLL, ROM or hardcoded game-specific code is published. New hardware/CPU implementations use the same identities and transport.

## v0.4.9.16 — cumulative recovery history

**Latest v0.4.9.23 contract:** COMPAT-023: the approved exact Windows `ESC[2K\r` Rizin console prefix is a recognized array boundary, without permitting generic CR or unknown ANSI. Audit hashes original bytes and records hypotheses, never verified code.


`analysis_integration` 0.3.1 now re-verifies and carries forward the immediately prior session's imported copied evidence plus its own new observations. It checks every ROM/mapper/P-code SHA and the original authorized tool evidence, never follows provenance paths, and enforces 64-item bound. Existing `--resume-from` schema remains compatible. See [release](../../releases/v0.4.9.16.md).

# analysis_integration — bounded analysis and native recovery providers

**Scope:** `production-workflow`. **Version:** `0.3.0`. Authoritative component registration: `workspace/components.json`. See [changelog](CHANGELOG.md).

`analysis_integration/providers.py` is the controller-owned compatibility boundary that requests authorized standalone Ghidra Z80 headless analysis and Rizin `aflj` function-boundary hypotheses. The active analyzer component owns maintained Ghidra/Rizin subprocess providers and validates source SHA-256 and per-instruction bytes before passing evidence into the C++ discovery and translation DLLs. Rizin cannot supply executable instructions; its function entries are merely hypotheses in the initial mapper context. An approved Ghidra backend is also re-invoked on genuine missing-code stops using an exact observed mapper-built 48 KiB view and the stopped PC. The resulting region is clipped to one original-ROM bank slot and every instruction is independently rehashed against the original ROM before submitting a bank-export to native C++ translation. Without an approved Ghidra executable, the bounded native source-discovery path still operates but may stop for insufficient coverage.

`analysis_integration/cli.py` implements a bounded compile-run-observe-recover pipeline called by compiled `RecompDev.exe --stage native-orchestrate`. It preserves per-attempt evidence outside Git source, refuses to overwrite existing directories, authenticates observed ROM+mapper+SP before generating the next candidate, rejects repeated gaps/no-progress loops and respects maximum rounds. The native application is built and executed from maintained active source, never `legacy/` or `baselines/` production code.

This source-only Python interoperability module is a **temporary analysis adapter**, not the eventual fully compiled provider ABI. Currently only the Master System/Z80 native translation backend exists; other hardware formats fail explicitly. No automatic external-tool installation is attempted. Full Windows real Ghidra/Rizin, autonomous 1,800-frame/gameplay and second real-ROM parity remain acceptance blockers.

## v0.4.9.12 — strict Rizin console compatibility

`analysis_integration/rizin_compat.py` is a self-contained, architecture-neutral parser for *successfully exited* Rizin `aflj` results that the immutable historical subprocess runner rejected because known `WARNING: invalid address from 0x...` diagnostics preceded its JSON array. Only documented bounded warning lines, whitespace and optional terminal SGR decoration are allowed; unknown diagnostics, malformed structures, trailing content, invalid offsets/sizes, oversized logs and hash mismatches **fail closed**. Preserve `analysis/rizin/rizin-output.log` exactly; write separate `rizin-aflj.json` and `rizin-compatibility.json` containing warning count, raw-log checksum, initial historical parser status and normalized payload checksum. Function records are boundary hypotheses only. The controller sees structured provider evidence rather than Rizin console formatting, and no CPU/ROM/console heuristics were added.

**Remaining debt:** Invocation still uses read-only `legacy/.../tooling.orchestrator::_attempt_rizin`; Ghidra uses frozen `nativeprep` and Ghidra scripts; source reconciliation and reading reuse preserved Python modules; the bounded recovery CLI is Python. This release deliberately does *not* claim those services are compiled plugins. See [legacy exit plan](../../architecture/LEGACY-EXIT-PLAN.md) for sequenced, test-gated removals.

## v0.4.9.13 — maintained Rizin provider v1

The active Rizin path now uses `analysis_integration.rizin_provider.execute_rizin`, not the read-only historical `tooling.orchestrator._attempt_rizin`. External-tool allowlisting also belongs to maintained `analysis_integration.tool_authorization`. The versioned Python provider contract is `recompdev.analysis.rizin-provider.v1`; invocation is explicit and synchronous with bounded merged console capture (2 MiB), 1–3600s timeout, process-tree termination, no shell, no user Rizin configuration, source and tool SHA-256 checks before/after execution, and explicit Z80/m68k/MIPS Rizin CLI mappings. This is **not yet a compiled DLL/ABI** and does **not** claim native support for the latter two CPU architectures.

For success it preserves original `rizin-output.log`, publishes `rizin-aflj.json`, `rizin-process.json`, and `rizin-provider.json` with original-log hash, warning list, ANSI formatting counts, function count and normalized export hash. An `ESC[2K` standalone erase-line sequence from Rizin 0.9.1, bounded SGR and recognized invalid-address warnings are accepted only in the prefix; no-warning JSON is also allowed. Unknown diagnostics, malformed records and trailing bytes are rejected. Failed tool runs retain raw output and process evidence, with no accepted normalized JSON. Function records are hypotheses only and never verified instructions.

**Legacy exit remains incomplete:** Ghidra's headless invocation/export Java scripts, reconciliation, Ghidra candidate selection and recovery/export parsing still reference the archived tree. This milestone removes the active Rizin execution/authorization imports **only**. The compiled controller still invokes the Python analyzer bridge. See `docs/architecture/LEGACY-EXIT-PLAN.md` for remaining enforceable gates.

## v0.4.9.14 — maintained Ghidra export and evidence reuse

The initial Ghidra launcher and headless Java scripts now live in `analysis_integration/ghidra_provider.py` and `analysis_integration/ghidra/`, with bounded process supervision, immutable logs, source/tool hashes and source-bound export identity. `ghidra_evidence.py` owns active byte-level export checks; `reconciliation.py` owns maintained, schema-compatible Ghidra/Rizin candidate merging. `analysis_integration` no longer imports frozen Python modules or loads scripts from `legacy/` for this path. Existing Ghidra language and validated bank-context constraints are unchanged.

`--resume-from PREVIOUS_RUN_DIR` explicitly requests **evidence reuse**, not restoration of executing process state. `recovery_history.py` reads a prior immutable `orchestration.json`, rechecks its ROM identity and each observed PC/mapper/physical address, rehashes every focused-bank Ghidra instruction against the ROM, verifies the stop instruction and associated audit and copies accepted seeds/overlays into `imported-history/` in the new output directory. The compiled controller and native translator still independently inspect the source. Old generated binaries are not reused, initial Ghidra/Rizin analysis may be repeated, and the previous output is never modified. The feature is opt-in and limited to authenticated SMS/Z80 translation evidence because that is the only implemented native translation backend; reusable import contracts are not license to assert MD/PS1 recompilation.

**Remaining debt:** Python `cli.py` still owns scheduling and invokes the compiled controller; other modules (production translation, discovery) retain frozen imports. This is not a C++ analysis ABI, universal machine support, or 1,800-frame/parity achievement. See [legacy-exit plan](../../architecture/LEGACY-EXIT-PLAN.md).

## v0.4.9.18 initial-analysis cache contract

`analysis_integration.analysis_reuse` is a temporary maintained Python provider. The initial Ghidra and optional Rizin outputs are reused only for immediately adjacent sessions with exact ROM SHA-256/size, provider-source/Java-script digest and approved executable pathname+bytes. Ghidra P-code instruction hashes are rechecked against original ROM. Rizin function guesses are independently reconciled. Missing cache contract (e.g. historical v0.4.9.17 evidence) causes a fresh analysis; mismatched source aborts and corrupted reusable input artifacts fail closed. Observed stop/bank exports still go through the independent cumulative source/mapper checks and native instruction admission. This is not a completed compiled analysis DLL ABI or reusable gameplay execution state.

## v0.4.9.20 preview-frontier compatibility adapter

The native controller can optionally pass one complete, source-attested preview diagnostic ZIP into the **first** newly resumed analysis cycle. The `analysis_integration.preview_frontier` verifier rechecks the ZIP manifest, original immutable generated `translated.cpp`, job/session/round, ROM digest and original native PC/physical/mapper/SP state. Accepted evidence enters `recovery_history` with distinct provenance; the compiled native discovery provider performs its normal byte/mapping validation again. No translated code is accepted merely from an address, and no previous session is rewritten. This remains Python tooling until a production compiled analysis ABI is qualified.

## v0.4.9.21 extended immutable cycle identity

Preview seed verification accepts bounded 2- or 3-digit cycle identifiers through 128, and still rejects incorrect source, mapper, ROM, session or original translation evidence. This does not make untrusted preview ZIPs replayable or authorize new providers.
