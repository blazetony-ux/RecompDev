# RecompDev — binding development contract

**Effective:** 2026-11-05, approved by the project owner before implementation of v0.4.9.7.
**Authority:** This document controls future development decisions and conversation handovers. Changes to it require a new pre-build report and explicit owner approval.

## 1. The product, not the test game

RecompDev's deliverable is a **compiled native `RecompDev.exe`** that orchestrates interchangeable, independently versioned **DLL plugins** for binary/container discovery, CPU semantics, hardware mapping, translation, native runtime and validation. The target is automatic native x86/C++ recompilation of software across multiple CPU and console families. Shinobi and other commercial games are validation inputs; no title-specific code, ROM hashes, hardcoded guest addresses or behavior patches are permitted in production plugins, controllers or backends. Such values may only exist as labelled test/evidence fixtures.

The controller owns dispatch, protocol selection and error/evidence reporting, but **not** CPU instruction semantics or console hardware behavior. The live monitor communicates exclusively with the controller, never with a CPU or hardware plugin directly. Versioned C ABI interfaces must validate API size, plugin kind and version and fail closed on missing capabilities. No undocumented assumptions about game structure or correctness.

## 2. Scripts and historical code

Use PowerShell for installation/build convenience and at most one optional launcher. Do **not** add PowerShell/Python wrappers as new production orchestration layers. Existing Python/Ghidra and full preserved P-code translation functionality may be used as an explicitly versioned temporary compatibility provider until safely replaced; these are not proof that the native compiled translation plugin exists. New implementation priorities must move actual native functionality into EXE/DLL code and reduce core script dependence, while retaining established results.

Do not discard or mutate the 581-file historical v0.4.0.45 source or 61-file modular harness baseline (`legacy/`, `baselines/`); preserve the 642-file integrity checks, prior original code, produced evidence and source-authorised recovery knowledge. Avoid rewriting external owner catalogue data and original game media. Reject unverified source bytes, uncertain banking, unproven instruction semantics and incomplete parity claims.

## 3. Mandatory approval gate before every build

**Before writing implementation code**, provide the owner with a full, versioned pre-build report covering (a) exact Git/source baseline, inventory and outstanding issues; (b) precise EXE/DLL/ABI/files and version changes; (c) genuine new discovery/translation/native execution functionality; (d) preserved historical code reuse; (e) explicit Master System/Shinobi continuity; (f) cross-game and cross-CPU synthetic acceptance; (g) risks, exclusions and rollback; (h) concrete, falsifiable acceptance criteria; (i) scripts, docs and handover changes; and (j) post-build accountability.

Await **explicit owner approval** before building. If implementation would materially deviate, halt and submit an amended report. Do not silently substitute documentation-only or Python-only progress for approved native deliverables.

The approved v0.4.9.7 report is stored **verbatim** at [PREBUILD-v0.4.9.7.md](PREBUILD-v0.4.9.7.md); approval occurred in the user conversation after that proposal.

## 4. Acceptance and release integrity

A release is not `INSTALLED`, `COMPLETE`, or `PARITY VERIFIED` simply because it compiled or produced reports. Require explicit versions/hashes of changed compiled EXE and DLLs, loaded-plugin evidence, independent tests of native interfaces, source-bound code discovery, translation/build/semantic verification, cross-platform fixtures, Windows multi-config `ctest -C Release`, historical preservation and clean source/rollback checks. Separately label tests run in Linux, owner Windows, synthetic inputs and commercial game executions. If a mandatory acceptance is absent, mark the build **CANDIDATE/BLOCKED** and list exactly what is unverified. Do not move a release tag or promote active binaries without successful gates.

At the end of every release, provide a before/after component-version table, exact shipped files, test pass/failure counts, SHA-256 for built artifacts, unchanged components, deviations from the approved scope and remaining limitations. Integrate that report into source-controlled release notes, changelogs and [HANDOVER.md](HANDOVER.md).

## 5. Shinobi continuity, always

The owner-validated baseline is v0.4.9.6, building on v0.4.9.5's 44/44 Windows CTest, successful independent controller-mediated Live Execution Monitor, deterministic input replay, source-verified recovery, retained historical 1,800-/2,400-frame observations (not gameplay parity), and observed static frame after about 574 in one recovery. The 2026-11-05 interactive Right-input evidence correctly reported guest port `0xDC=0xF7` but showed perceived reversed scrolling and an untranslated stop at `0x4F9E` near frame 730. These remain unresolved. Never call previously observed stops such as `0x7BE8` newly discovered without checking historical evidence. Do not claim any unrelated discovery build repaired scrolling, untranslated code, or native gameplay correctness.

Every future handover must explicitly identify (1) implemented and tested native features, (2) current Shinobi regression and open problems, (3) remaining compiled-versus-Python gaps, and (4) the next verified universal development milestone.

## 6. Automated governance

Documentation governance checks the existence of this contract, the approved pre-build report in release docs, a handover pointer, and release compliance disclosure. Automated checks can catch omission, not certify correctness; human approval remains mandatory.

## 7. Permanent release installer (owner-directed v0.4.9.8 amendment)

Every approved source release uses **one Git-managed root installer** `Install-RecompDev-Release.ps1`, plus one hash-pinned ZIP containing changed source files and the manifest. No per-release PowerShell installer variants or manual file overwrites. Verify the exact committed Git baseline, safe ZIP content and independently supplied package SHA-256; stage and test outside the source tree; commit, tag, bundle and activate verified native binaries only after required acceptance. Retain transactional rollback. Candidate validation must never overwrite the active Shinobi runtime or be called an installed release. This addition was explicitly requested and authorised by the owner on 2026-11-05; see [PREBUILD-v0.4.9.8.md](PREBUILD-v0.4.9.8.md) and the [permanent release process](../development/RELEASE-PROCESS.md).

## 8. Owner-approved discovery-release promotion decision (2026-11-06)

After the owner supplied successful 45/45 Windows CTest, 642 historical-source and all Python/docs validation evidence, they requested a genuinely **installable v0.4.9.8 ZIP with commit, tag, backup and activation** before any further development. The release is now explicitly scoped to the verified native discovery, controller/plugin ABI extensions and permanent installer. The previously approved **real-ROM -> preserved P-code -> compiled native game** acceptance is retained as the mandatory *next engineering milestone*, not presented as delivered in v0.4.9.8. All future builds again require a pre-build report and owner approval. See [v0.4.9.8 amended prebuild](PREBUILD-v0.4.9.8.md) and [release record](../releases/v0.4.9.8.md).

## 9. Owner-approved v0.4.9.17 separated infrastructure release (2026-11-07)

The owner explicitly approved a separate **`infrastructure-source`** release track, constrained to **`git-main-only-no-runtime`**, for independently validated controller, documentation, workspace, diagnostic and migration infrastructure. The permanent Git-managed installer may commit and tag these source changes onto `main` only after complete Windows regression tests, 642-file preservation and mandatory promotion checks. It must not overwrite any currently active production EXE, DLL or runtime lockfile; no automatic remote GitHub push. Validation alone never installs the source release. Source-only installation requires explicit `-Mode Install` after acceptance and retains transactional rollback. This is not approval to bypass acceptance checks.

The **Shinobi 1,800-frame** deliverable, independently checked semantics, input/VDP/PSG/IRQ/mapper timing, at least one unrelated real ROM, ROM-independent native game and compiled analysis ABI remain **BLOCKED** and are mandatory before **gameplay-runtime qualification**. A frame count reached without independent parity is not qualification. All pending legacy functionality must remain in the capability register until separately demonstrated; frozen `legacy/` and `baselines/` bytes are never changed.

## 10. Owner-requested v0.4.9.18 targeted recovery and evidence-root release (2026-11-07)

After the v0.4.9.17 main/tag GitHub publication and the owner's successful upload-ready diagnostic ZIP, the owner requested a focused build fixing three remaining infrastructure issues: versioned evidence storage under `C:\Projects\RecompDev-Evidence`, compact translated-instruction differences in a single ZIP, and source/tool-attested reuse of unchanged analysis while prioritising genuine observed recovery frontiers. This request authorises the code and documentation change, not relaxing the architecture or gameplay qualification. `-Mode Install` is permitted only after full owner Windows tests, historical file gate and independent source-only acceptance; production binaries remain unchanged. Unqualified real 1,800-frame Shinobi/second-ROM/hardware parity and compiled analysis ABI remain separate mandatory future gates.

## 11. v0.4.9.19 preview is not recovery or gameplay qualification (2026-11-07)

The owner requested restoration of the useful live instruction window alongside native gameplay preview and pressed-Z stop evidence. Implement it as an opt-in **generic controller preview** using the existing controller diagnostics subscription service. Z80/SMS details stay in their replaceable machine and presentation adapters, and viewer code must never directly read CPU/VDP memory. Preview must use an isolated source-attested generated-project copy, not modify the authoritative compiled recovery session, job state, source ROM or any active DLL. Reports must distinguish temporal input-to-stop association from proven causality. Store all substantial preview output and upload-safe diagnostics under `RecompDev-Evidence/v0.4.9.19`, reserving AppData for lightweight configuration only. Validate current Windows gameplay/monitor-window functionality with owner evidence; source-only infrastructure promotion cannot waive 1,800-frame Shinobi and independent semantic/hardware parity gates. The mandatory approval and release process remain in force.
