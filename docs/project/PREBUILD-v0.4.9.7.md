# RecompDev — v0.4.9.7 pre-build proposal

**Status:** PROPOSED — **NOT BUILT OR APPROVED**  
**Proposed release theme:** Native Controller, Interchangeable Discovery DLLs & Source-Verified Code Progression  
**Reference baseline:** owner-validated `workspace/v0.4.9.6`, Git commit `7243e62851684477764117398b48ee335673eac2` (44/44 Windows CTest).  
**Prepared from:** available v0.4.9.6 staged source, earlier source archive, owner validation log, and documented runtime/recovery evidence. No claim of current live access to the owner's Windows checkout.

## 1. Why this build is necessary

The requirement is a **compiled `RecompDev.exe` that orchestrates interchangeable native DLL plugins** to discover and translate different source binaries into native x86 C++ outputs. PowerShell may install/build and one convenience launcher may exist; Python may be used as an external research tool, but it must not keep accumulating as the permanent controller architecture.

The present `controller/main.cpp` is still labelled 0.4.4 and forwards commands to `modular/cli.py` or `workspace/manager.py`. Existing `rd_discovery_jsonl` is an event **recorder**, not a structural code-discovery engine. The existing `rd_cpu_z80` DLL implements a restricted synthetic-fixture interpreter and source-length gate, while the production native C++ lowering still uses the preserved v0.4.0.45 P-code generator. v0.4.9.6 added Python discovery-audit providers without changing compiled DLLs.

A build that merely changes version strings, adds another Python workflow, or produces another audit with zero new work **fails the goal**.

## 2. Deliverables proposed for v0.4.9.7

### A. Native controller owns the discovery request

- Update C++ `RecompDev.exe` to load and validate native plugin DLLs directly (ABI version, plugin kind, API struct size, required callbacks, deterministic selection, explicit errors).
- Implement a **native `discover` command path** without launching `modular/cli.py`; other existing commands continue to work through clearly marked compatibility routing until separately migrated.
- Separate and report the workspace release version from the controller's internal binary/API version. Report loaded DLL names, API versions and hashes in machine-readable evidence.
- Accept source file paths containing spaces, preserve source bytes, and write results only under an evidence directory.

### B. Replaceable structural discovery DLLs

- Add a **versioned C ABI for structural discovery**; do not confuse it with the existing `RD_DiscoveryApi` JSONL event recorder.
- Implement reusable source/container detection through DLLs: SMS/raw Z80 cartridge properties, Mega Drive header/vector properties, and PlayStation 2048/2352-sector logical file/executable inspection via qualified historical algorithms.
- Own platform-specific format rules inside the appropriate plugin, never in the controller and never by recognising a game title, known ROM SHA or hardcoded game code address.
- Report *detected*, *verified*, *not applicable*, *unsupported*, *blocked* distinctly. A successful process exit is not evidence of successful executable extraction.

### C. Real source-verified **Master System code-discovery progression**

- Extend the compiled Z80-side discovery/decoding contract, initially as a separate interface rather than pretending the existing interpreter supports the full ISA.
- Starting from structurally valid reset/interrupt entry seeds plus independently verified existing candidates, walk **unambiguous** reachable code and emit function/basic-block and control-flow edges; preserve uncertainty for data/code overlap, indirect branches, unverified IX/IY lengths, bank mapping and unresolved dynamic targets.
- Bind each accepted instruction or block to its physical source offset and exact source bytes/hash. Use an SMS memory-mapper provider for guest-to-physical resolution; the controller remains CPU/machine neutral.
- Consume previously recorded native execution/recovery evidence to queue unresolved addresses generically, deduplicate source-attested work, and output new coverage and unresolved-item deltas.
- Integrate the verified discovery queue with the **existing full, preserved P-code translation backend** via a **limited compatibility adapter**, so at least one newly admitted generic Z80 block can be exercised through the native project generation/compilation tests. Do not substitute an incomplete new translator or game-specific opcode patches.
- Publish separate counters for freshly verified instructions, reused cached instructions, rejected/uncertain candidates, new verified blocks, unresolved branches/bank mappings, translated blocks, and compiled/verified native blocks. An increase in discovered candidates alone is not translation proof.

### D. Continuity, not regression

- Preserve existing game execution, runtime host, SMS video DLL, source-authorised recovery, replay and live execution monitoring.
- Preserve the 642 frozen original files under `legacy/` and `baselines/`, with hash checks and rollback.
- Carry forward the established Shinobi reference: validated monitor; deterministic replay at `0x7BE8`; recovered 1,800-frame budget with static image after roughly frame 574; historical 2,400-frame evidence; interactive Right-input `0xDC=0xF7`, anomalous scrolling, untranslated stop `0x4F9E` around frame 730. These are **not** proof of gameplay parity.
- No source changes based on Shinobi-specific or Sonic-specific function addresses, hashes, inputs or filenames. Real games are validation inputs only.

### E. Documentation and build governance

- Ship native plugin ABI and ownership documentation, exact EXE/DLL version manifest, produced artifact hashes, and a before/after capability table.
- Include the **approved pre-build report verbatim** with the release history; flag every deviation with reason and approval before implementing out-of-scope work.
- Require newest-first changelogs, source provenance, historical preservation and a reproducible Windows installer (one PowerShell installer and at most one optional launch wrapper; no new sprawling PowerShell/Python runtime interfaces).

## 3. Planned native artifacts and their role

These are **proposed target component versions** (not yet built, installed or finalised):

| Artifact | Proposed component version | Expected change and why it matters |
|---|---|---|
| `RecompDev.exe` | **0.4.4 → 0.4.5** | Recompile with native discovery orchestration and DLL selection; stop Python forwarding for `discover` |
| `rd_cpu_z80.dll` | **0.2.0 → 0.3.0** | Recompile with independently versioned, source-verified decode/discovery API; preserve interpreter and admission compatibility |
| `rd_machine_sms.dll` | **0.1.0 → 0.2.0** | Recompile with mapper-backed physical source-location/discovery API; preserve the runtime bus ABI |
| `rd_format_sms.dll` | **new 0.1.0** | Structural SMS/cartridge format inspection plugin |
| `rd_format_md.dll` | **new 0.1.0** | Structural Mega Drive/68000 cartridge and vector inspection plugin |
| `rd_format_ps1.dll` | **new 0.1.0** | Qualified PS-X EXE, ISO and raw-sector disc inspection plugin |
| Existing `rd_runtime_host`, `rd_video_sms_mode4`, audio DLLs | **no proposed version change** | Avoid destabilising verified Shinobi native gameplay path |
| Preserved P-code backend | **compatibility implementation, not a new DLL** | Reuse through constrained interface until safely migrated; do not pretend translation is now a native DLL |

A DLL's **version number must change when its ABI or implementation changes**, and the release must supply hashes and the corresponding test evidence. Mere existence of a DLL without actual controller-driven use does not satisfy the milestone. If file/ABI layout has to change during implementation, the amended artifact and version table must be approved before release.

## 4. Test and acceptance matrix

**Must all pass before calling the release installable:**

1. Existing **44/44 Windows CTest** regressions and existing Python research/monitor tests remain green; all 642 protected historical files remain byte-identical; rollback succeeds after an induced failure.
2. Native `RecompDev.exe --stage discover` succeeds on **synthetic Z80, 68000 and PS-X EXE/ISO fixtures** **without invoking Python** and records the actually loaded DLLs; wrong ABI/kind, missing plugin, malformed disc and corrupted source fail closed.
3. The native Z80 component discovers verified basic blocks and branch edges from fixture bytes; rejects ambiguous prefix and unresolved mapping cases without fabricated confidence.
4. Re-running the same source is idempotent: no fake fresh work; changing a source byte invalidates or rejects stale physical-offset work. Cached versus new entries are distinguishable.
5. **Actual native port progression, not merely auditing:** demonstrate at least one newly admitted, source-verified Z80 block from a **real Master System input** moving into the preserved translation path and through a native C++ build, with evidence of each transition; separately verify executable semantics on synthetic/reference-tested blocks. If the real-source transition or synthetic execution verification does not work, the release is **BLOCKED**, not relabelled as successful discovery-only work.
6. Exercise the *same* generic discovery path on **at least two different Master System games** from the owner's library (e.g. Shinobi and Sonic) plus Mega Drive Sonic and PS1 Ridge Racer, without per-title code branches. Real-game results are reported as observation, not assumed parity.
7. Existing Shinobi monitor and deterministic recovery workflows remain callable, and the release documents any actual coverage delta. The scrolling anomaly and `0x4F9E` remain open until independently verified; no invented improvement claim.
8. Windows-native test includes DLL load/unload, open file/SQLite handle cleanup, spaces in paths, multi-config `ctest -C Release`, and detailed compiler stderr on failure (lessons from v0.4.9.5 and v0.4.9.6 installer failures).

**Performance/evidence:** Record per-phase elapsed time, source coverage, new versus reused verified blocks, builds attempted, cache hit/reuse and native translation test outcome. No performance-win claim without a comparable baseline.

## 5. Explicit non-goals

- Complete 68000/MIPS native games, playable PS1/Mega Drive hardware, all Z80 opcodes, universal asset extraction or full gameplay parity in this release.
- Deleting or rewriting preserved history, abandoning the full P-code translator, adding ROM-specific patches, inventing CPU semantics or adding a new Python runtime controller.
- Declaring an EXE/DLL migration complete simply because the old Python workflow can still be launched from the EXE.

## 6. Risks and controls

- **Legacy generator coupling:** direct native discovery output may not fit the historical generator's expected IR. Bridge via a strict versioned evidence adapter; fail explicitly if semantics cannot be verified. Do not replace the full generator with a toy emitter.
- **Banked execution and dynamic branches:** conservative coverage only; uncertain addresses remain unresolved. Hardware-specific mapping stays in the machine plugin.
- **Release size:** if scope proves too large, return with a **revised pre-build report for approval** rather than silently delivering a reporting-only or Python-only build.
- **Windows portability:** test MSVC/CMake behavior early; all file handles closed before cleanup; do not depend solely on Linux acceptance.
- **Project handover:** write outstanding failures and actual capabilities into versioned documentation, with direct evidence references.

## 7. Release review and approval policy

For **every** subsequent RecompDev build, **before writing or modifying the release code**, provide a versioned pre-build report covering: baseline and actual module inventory; problem and user-facing improvement; precise EXE/DLL/plugin changes; reused historical code; translation/discovery/runtime deliverables; cross-game and synthetic tests; explicit exclusions; risks/rollback; measurable acceptance criteria; documentation/handover changes; and an itemised after-build result. Obtain the owner's approval of that scope first. Any material expansion or substitution requires an amended report before proceeding. Do not claim a release or binary works until the corresponding test has actually executed.

**Decision requested:** Approve, revise, or reject this proposed v0.4.9.7 scope. **No v0.4.9.7 code or installer has been built under this proposal.**
