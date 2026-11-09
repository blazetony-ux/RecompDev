# v0.4.9.26 autonomous preview-stop recovery — amended implementation scope

**Baseline:** `ff5d9dc589dbb948b56a6159482330c6d77404c9` (`workspace/v0.4.9.25`), provided 2026-11-08. **Approval context:** owner requested generic untranslated-code recovery and said "build it" after the integrated design discussion. This record does not establish release promotion or Windows test success.

## Problem / evidence

Interactive Shinobi preview reached an untranslated physical code location after observed button A (Z) input. The diagnostic stop was `UNTRANSLATED_INITIAL_CODE`, guest PC `0x052A`; the instruction's known Z80 semantics alone do not imply compiled program coverage. Existing `preview --job` produces an authenticated stop ZIP; `resume --preview-stop` was manual and the job scheduler returned early if a prior neutral run had reached the frame budget. The recovery compatibility provider uses neutral input, so it cannot prove an input-triggered frontier was passed.

## This candidate's implementation

1. Introduce **opt-in** compiled-controller `preview --auto-recover` dispatch. After a source-identified preview gap, use an immutable machine-neutral receipt, re-attest its ZIP and schedule one or more bounded existing native analysis/compile/recovery cycles. Fail closed on non-gap, absent exact input evidence, archive mismatch or source change.
2. Permit fresh source-attested preview-gap evidence to extend previously frame-budget-complete jobs without treating an old neutral-input target as qualification. Do not alter prior session bytes.
3. Persist a bounded exact guest-cycle input timeline in controller preview diagnostics and validate it in the source-bound preview verifier. The compatibility orchestrator replays this timeline for the new native execution run; neutral-input runs remain unchanged.
4. Keep CPU opcode semantics in reusable plugin implementation; add no title-specific ROM hashes, addresses or patches. Keep the existing source-attested Ghidra/P-code/native translation providers in place.
5. Add regression tests covering success, previous terminal-job reopening, absent replay or tampered input, unchanged original job on rejected evidence, and source-bound restoration of playback input.

## Changed components and interfaces

- `controller/native_job.cpp`: controller CLI flag/receipt validation, preview-stop recovery scheduling; no CPU-specific semantics.
- `execution_monitor/job_preview.py`: transitional preview evidence service writes bounded input replay + immutable completion receipt. No new Python orchestration layer.
- `analysis_integration/preview_frontier.py`, `analysis_integration/cli.py`: compatibility provider validates/uses recorded replay as input on subsequent native runs.
- `analysis_integration/tests/test_v04920_preview_frontier.py`, `controller/tests/job_manager_contract.cpp`: evidence + compiled orchestration regression cases.
- `controller/main.cpp`: CLI usage text only.
- `docs/project/HANDOVER.md`, release note: candidate limitations and Shinobi regression.

**Binary change:** `RecompDev.exe` must be rebuilt. Existing generic CPU/machine DLLs are unchanged. No ABI version claims are made for installed binaries; promotion only after independent Windows build/testing. Existing C ABI remains unchanged.

## Explicit exclusions and risks

- This is the **first bounded native-controller recovery slice**, not a fully universal hot-swappable DLL manager. It recompiles the existing SMS native app through the transitional provider and replays inputs; no in-process DLL patching or new 68000/MIPS execution ability.
- A stop may arise from an unsupported hardware state; the provider must fail closed. Replaying guest-cycle input is not a full CPU/device checkpoint and does not prove gameplay parity.
- The existing `sms`/`z80` compatibility provider remains a blocking generality issue; no bypass is permitted.
- `preview --auto-recover` may append an immutable session, but must not overwrite source, original ROM, old session, active runtime or shared cache without existing verification.
- Shared artifact location remains owner-established `C:\Projects\RecompDev-Artifacts\store\v1` when configured; no new top-level Windows directories.

## Falsifiable acceptance

- C++ scheduler contract test exercises a completed job plus an authenticated new input stop and proves an additional provider batch receives the original preview stop.
- A tampered/missing replay is rejected **before** recovery-job mutation.
- Python verification rejects changed ZIP member hashes or malformed replay events, and uses the same exact cycle stream for native execution.
- Existing historical 642-file manifest remains unchanged; no test-title branches in production.
- Actual Windows `ctest -C Release`, source SHA gate, tool dependencies, real game interactive recovery and cross-game/cross-CPU acceptance are **not claimed until owner tests**.
- Shinobi 2,400-frame gameplay and video/audio/input parity remain **UNVERIFIED** until independently observed.

## Rollback and promotion

Ship only a hash-locked changed-source package following the single existing `Install-RecompDev-Release.ps1` protocol; no release/tag/runtime activation without Windows acceptance and an explicit promotion decision. Keep all active binaries in place. Source baseline and prior artifact-store bytes must remain untouched during candidate validation.
