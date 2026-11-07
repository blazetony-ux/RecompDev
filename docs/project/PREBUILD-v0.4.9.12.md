# RecompDev — PREBUILD v0.4.9.12 (owner-approved compatibility scope)

**Date:** 2026-11-07  
**Status:** Owner approved implementation in conversation on 2026-11-07; built source candidate, Windows installation/promotion pending  
**Purpose:** Correct the active analysis-provider handling of valid Rizin `aflj` JSON preceded by non-JSON analyzer warnings. No game-specific or CPU-specific instruction changes.

## A. Exact baseline, inventory and failure evidence

- Verified original Git baseline recorded by the v0.4.9.11 release manifest: `workspace/v0.4.9.9`, commit `53c42ec3b8f50f26a9dca6fbce5300fa1d9d1c63`.
- Verified candidate release: `workspace/v0.4.9.11`; release transaction `20261107T113515Z-40616`; output source root `C:/Projects/RecompDev-ReleaseStage-20261107T113515Z-40616`.
- Verified both uploads: the release-transaction payload and separately uploaded release-stage source agree byte-for-byte for all **78 manifest-declared source files**, and all 78 match their SHA-256 values.
- v0.4.9.11 is explicitly a **non-promotable validation candidate** (`promotion_eligible=false`). The user has run its staged `RecompDev.exe`, but this does not establish installation into the live Git checkout.
- The owner tested a real Shinobi ROM against approved Ghidra and Rizin v0.9.1. Rizin exited successfully; its combined log is 266,579 bytes. The leading text contains two `WARNING: invalid address from 0x...` lines. After removing 89 preceding characters, Windows PowerShell `ConvertFrom-Json` successfully parsed **244 function records**. This proves the specific leading-prefix parsing issue, not analysis correctness or gameplay parity.
- The active `analysis_integration/providers.py::acquire` invokes the historical `tooling.orchestrator::_attempt_rizin` and then refuses the result if its status is not `EXITED`. `_attempt_rizin` applies `json.loads()` to the complete combined `rizin-output.log`, which is the immediate incompatibility. The original raw log is preserved.
- No native translation round started in the failed run. The Master System `rd_format_sms` detection worked. Existing Shinobi execution/graphics/input/audio acceptance blockers remain open.

## B. Exact proposed files and versions

| Component | Prior | Proposed | Notes |
| --- | --- | --- | --- |
| `analysis_integration` compatibility adapter | `0.1.0` | `0.1.1` | **Only production behavior change**; bounded, strict Rizin JSON separation at the active provider boundary |
| `controller` / `RecompDev.exe` | `0.4.10` | `0.4.10` | No ABI or C++ source change |
| Other compiled DLLs | v0.4.9.11 manifest versions | unchanged | No CPU/format/machine/translation/runtime modifications |
| Worktree release | v0.4.9.11 candidate staged on v0.4.9.9 | v0.4.9.12 candidate | Not installed or promotable without separate acceptance |

Proposed changes in source staging:

1. `analysis_integration/providers.py`: add an adapter-local, bounded recovery path for precisely delimited `aflj` array output in a Rizin process log when the preserved legacy runner reports `UNPARSABLE_JSON` after a successful exit. Do **not** modify the frozen runner.
2. `analysis_integration/tests/test_native_orchestration.py`: extend the subprocess mock to reproduce leading Rizin warnings on Windows/Linux and assert the real controller analysis/orchestration path proceeds to source verification.
3. `analysis_integration/tests/test_rizin_output_compat.py` (new): executable regression tests for real warning format, empty/large lists, malformed JSON, unrelated non-JSON prefix/trailing garbage, unsupported/malformed function objects, limits and evidence preservation.
4. `workspace/components.json`, `docs/components/analysis_integration/{README,CHANGELOG}.md`, `docs/releases/v0.4.9.12.md`, `docs/project/{HANDOVER,ROADMAP}.md`, and `CHANGELOG.md`: version/status/acceptance reporting as necessary; no changes to the binding development contract.
5. Generate candidate source package and manifest via the **existing** permanent `Install-RecompDev-Release.ps1` protocol, not a new installer; record the exact package SHA-256 and restore/rollback instructions. Do not mutate active Git or binaries during candidate validation.

## C. Adapter contract and security requirements

- Preserve `analysis/rizin/rizin-output.log` unchanged as the authoritative raw subprocess record, including warnings. Never overwrite that path during reparse.
- Read bounded bytes, reject oversized/unreadable log, and identify exactly one top-level JSON list using a real JSON decoder; permit only a strictly documented small diagnostic prefix matching known Rizin warning format, and whitespace after the array. Reject unexpected preamble, extra JSON objects, trailing errors, or malformed values.
- Require a list no larger than the existing analyzer limit (20,000 function hypotheses), with valid typed `offset`/`size` and defensible ranges following existing `tooling.analysis.parse_rizin` contract. Do not treat Rizin function boundaries as executable P-code or bank proof.
- Produce separate normalized `rizin-aflj.json` and machine-readable warning metadata (warning count/type and a reference/hash to the raw log). Preserve the initial `UNPARSABLE_JSON` parser status in audit metadata while marking the active adapter's verified normalization explicitly; do not falsely claim a clean console or hide analysis warnings.
- If anything is ambiguous, still fail closed. Only use this path when the approved subprocess completed successfully; no bypass of executable allowlists, ROM SHA-256 verification, Ghidra instruction-byte hashes, or compiled translator verification.
- No game/ROM-specific SHA, title, address or patch is admissible in production code.

## D. Native functionality and historical preservation

This is an **integration correction**, not a new native CPU translator or parity milestone. It restores access to Rizin boundary hypotheses already emitted by the approved external tool. Ghidra remains responsible for byte-attested P-code; the compiled native discovery/translator DLLs remain authoritative for admission and translation. Preserve all 642 frozen files under `legacy/` and `baselines/`, including the older `_attempt_rizin` implementation. No production dependence on an additional orchestration wrapper will be added. Temporary Python compatibility remains an explicitly disclosed architectural gap.

## E. Shinobi continuity and cross-platform acceptance

- Re-run the owner-approved real Ghidra/Rizin analysis against the same source-verified Shinobi ROM in a **new evidence directory**, never over the failed run. Expect raw warnings to remain visible and a valid 244-function *Rizin analysis payload* if the installed analyzer and inputs remain unchanged; variations must be investigated, not ignored.
- Verify the translated native pipeline starts rather than failing on the Rizin JSON boundary. Starting translation is **not** proof of successful 1,800-frame gameplay parity.
- Retain Shinobi baseline issues: observed untranslated-code stops, scrolling/input uncertainty and graphics/input/audio mismatch validation remain unresolved.
- Exercise synthetic, **source-distinct** Master System test inputs in the existing orchestration harness. Add parser-level architecture-neutral fixtures for boundary records and strict warning handling. Do not claim native Mega Drive/MIPS translation exists.
- Confirm Windows Rizin 0.9.1 warning-prefixed output and ordinary warning-free output, including normalized JSON field semantics and evidence integrity.

## F. Mandatory tests and measurable acceptance

1. New pure-Python parser regression suite passes: valid warning-prefixed JSON, ordinary JSON, warnings retained, malformed/trailing/unexpected prefixes rejected, malformed object and caps rejected.
2. Existing `v04911_controller_analysis_recovery_integration` tests pass using mock external subprocesses and two unrelated synthetic ROMs. Verify the true compiled-controller path (`RecompDev.exe --stage native-orchestrate`) and that analysis reports reflect warnings.
3. Existing focused v0.4.9.10+ tests and historical-preservation governance pass; validate exactly **642/642** frozen historical files.
4. Full Windows MSVC build and `ctest -C Release` pass; Linux tests may be reported separately but never substituted for Windows acceptance. Track the known original-archive local Linux blockers individually rather than mark them as passed.
5. Validate-only package through the **permanent** installer passes baseline and manifest/ZIP hash checking with no modification of active live source or binaries.
6. Actual Windows real Rizin/Ghidra run produces `rizin-aflj.json`, warning evidence, reconciled candidate output and initiates at least one compiled native translation attempt. Output has clean SHA-256 provenance and new evidence directory. Do not claim end-to-end native parity from this alone.
7. Every generated artifact has listed hashes; source/compiled component versions before/after, test counts, rollback, unchanged modules, deviations and remaining blockers go into release notes and handover.

## G. Risks, explicit exclusions, rollback

- **Risk:** Interleaved stdout/stderr can contain errors or extra material; strict parsing must reject any output that is not an approved warning prefix plus exactly one complete JSON array. Warnings about invalid addresses remain quality signals, not proof all 244 boundaries are meaningful.
- **Risk:** Tool versions may change output format; unknown formats must fail closed until independently verified.
- **Risk:** Staged v0.4.9.11 differs from the actual live v0.4.9.9 Git checkout. Package must contain the complete manifest-declared delta from the installed baseline or otherwise follow an approved sequential installation plan. Do not apply standalone source overlays to the live repository.
- **Risk:** A v0.4.9.12 adapter-only correction cannot justify the promotion of v0.4.9.11/12 while mandatory native parity and multi-platform acceptance remain unmet.
- **Exclusions:** No edits to commercial ROMs, frozen sources, Z80 instruction semantics, SMS memory mapper, MD/PS1 runtime support, original controller ABI, native graphics/input/audio, or generated native game behavior.
- **Rollback:** No live changes during Validate. The existing transactional installer must preserve original Git/binaries and external Git bundle if a separately approved Install transaction ever occurs. Failures leave the live release untouched.

## H. Post-build accountability / approval gate

Deliver a precise source ZIP + independently provided SHA-256; report modified file hashes, C++ binary hashes (or explicitly unchanged), actual Windows/Linux test counts, real-tool results versus synthetic tests, 642-file integrity and any unverified acceptance items. Mark release **CANDIDATE/BLOCKED** until its explicit gates pass. No stable promotion based solely on JSON parsing success.

**Owner approval required before implementation:** Approve **v0.4.9.12 Rizin output compatibility candidate** with the scope, constraints and acceptance gates above. Any material scope change must return for approval. This draft itself changes no project source files, installer or release state.

**Owner amendment:** Explicitly require a phased zero-legacy-dependency transition over subsequent builds. This candidate must not present the adapter-only correction as the completed native provider architecture. See [legacy exit plan](../architecture/LEGACY-EXIT-PLAN.md).
