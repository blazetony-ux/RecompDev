# RecompDev workspace changelog

## [workspace/v0.4.9.27] — incremental native-code library and independent generated-source Git (owner-accepted SOURCE-ONLY promotion)


- **Working-preview acceptance and promotion governance (2026-11-09):** Owner Windows `Validate` transaction `20261109T190156Z-25652` passed **89/89 MSVC CTests**, 47 Python governance/migration/release tests, documentation governance and **642/642** protected-history checks. Fantasy Zone reached its **2,400-frame** target, published a consolidated native DLL, then replayed the tested path with **zero recovery pauses** and matching 2,400 frame hashes; later interactive play added eight verified regions. The owner confirmed arrow-key/Z gameplay and corrected scrolling in Fantasy Zone and Shinobi, with Shinobi showing live gameplay and a reported 2,400-frame completion. No independent audio output or hardware/semantic parity qualification exists. Per the existing `infrastructure-source` release policy, the owner approved **source-only Git promotion**, not an unqualified active runtime replacement; `-Mode Install` must create and verify the Git commit/tag/bundle while preserving active runtime binaries and its lockfile. The validated transaction executable remains available separately for working-preview use. No ROM-free game executable is delivered.

- **Fantasy Zone 1,968-frame recovery-limit correction (2026-11-09):** Owner MSVC candidate `20261109T174159Z-25652` passed **87/87 Windows CTests** and all 642 preserved-history checks, but real Fantasy Zone stopped after 1,968/2,400 frames when a hidden 64-frontier cap rejected PC `0x3A9D`. This candidate lifts the small lifetime cap to an explicit **512 per-session recovery budget**, uses bounded indexed evidence for 65+ native discovery/consolidation (avoiding Windows command-line growth), and attempts consolidation after controlled BLOCKED outcomes as well as normal exit. Delta translation now considers the current source-attested frontier rather than repeatedly passing historical paths. A compatible rebuilt base can be regenerated from old per-ROM source history when a new controller/VDP binary invalidates the old DLL fingerprint; old artifacts are never silently hot-loaded or deleted. **No claim of unlimited resources or completed Windows acceptance.**
- **SMS Mode 4 scrolling:** The independently replaceable video DLL now applies R8 shift in the hardware direction, R0 top-16 horizontal-scroll inhibit, rightmost 64-pixel vertical-scroll inhibit, fine-scroll backdrop and leftmost-8-pixel masking. Focused native pixel regressions cover these registers. The current framebuffer ABI still samples one register set per completed frame: raster-timed register changes, scrolling image parity, sprites and real two-window playability remain **unverified** and can still be incorrect.
- **Regression scope:** Added a native 72-distinct-frontier index test and scrolling pixel test, plus a generated-history rebuild test after simulated binary fingerprint change. Linux targeted end-to-end cache/reuse checks pass; owner must rerun the permanent Windows Validate and real Fantasy Zone 2,400-frame acceptance before install, main Git commit or immutable `workspace/v0.4.9.27` tag.
- **Windows source-history MAX_PATH correction (2026-11-09):** Owner `Validate` transaction `20261109T171415Z-25652` compiled MSVC successfully and preserved 642 originals, but only **85/87 CTests passed**: both new live tests failed after the first activation because the per-ROM Git history was nested under a long versioned evidence directory (`WinError 3`). Generated-source Git, compiled-module capsules and consolidated DLLs now live under short, separate `RECOMPDEV_HOME/gs`, `RECOMPDEV_HOME/nc`, `RECOMPDEV_HOME/nl` roots, with full ROM/module/binary SHA-256 directory identities and a conservative Win32 path preflight. The result is a new source-only candidate; full Windows 87/87 validation and real-ROM 2,400-frame acceptance still required.
- **Real-ROM diagnosis:** Owner's first Fantasy Zone v27 Windows run reached 621 frames with 20 activated compiled DLLs and 21 observed missing-code requests. Individual recoveries repeatedly rebuilt the cumulative translation; at the 21st recovery a missing `.obj` caused `LNK1181` close to game-window closure. The cause/timing of that linker failure is not conclusively established. The owner had earlier passed **85/85 Windows CTests**, but the real-ROM 2,400-frame responsive-gameplay gate FAILED.
- **Incremental live native code:** Added a backward-compatible translation-provider delta interface and an exact source-/bank-/instruction-byte-verified coverage-exclusion manifest. Each new hot-loaded module contains only previously uncompiled code; the controller dispatches among the initial module, reusable base and independently verified deltas without recompiling the growing cumulative code on every pause.
- **Persistent activated modules:** The guest emits an immutable source- and request-bound activation receipt only after successful native module verification and same-process activation. The controller then atomically publishes generated C++, translation manifests, DLL and checksums to a per-ROM immutable cache, even before completing the requested frame count. Closing the guest during a compile cancels the compiler process tree rather than leaving orphan build processes.
- **Per-ROM generated-source Git history:** Controller-owned source checkpoints are maintained in an isolated, ROM-SHA-indexed Git repository (never the RecompDev application source tree). Git records generated C++, source discovery, source hashes and toolchain fingerprint; binary artifacts stay outside Git. Source is saved after each confirmed activation; Git commits are periodic and at normal session completion. No ROM bytes are committed.
- **Consolidation and reuse:** At normal session completion, the controller takes verified accumulated source discoveries, creates one source-attested consolidated native DLL, validates coverage, records a generated-source commit and atomically publishes a SHA-verified pointer to the immutable DLL. On the next session it validates and preloads the consolidated base before executing new code. Consolidation currently performs one offline cumulative native translation/build, **not object-only relinking**, and is not a prerequisite for live game recovery. An interrupted session keeps its confirmed per-module artifacts and can consolidate them on a later successful session.
- **Input handling:** The Windows message loop preserves key-press transitions during native-code compilation pauses for delivery when guest execution resumes; this is not yet a demonstration of responsive live gameplay.
- **New regression evidence:** Linux native build PASS; synthetic two-gap recovery-and-preload test PASS; native source/Git/cache integrity test PASS; three-session interrupted/reuse/consolidate test PASS. The previously run 85-test Linux suite passed 83/85; its two source-preservation tests were blocked by a historical original-archives ZIP absent from this sandbox, not a reported source byte mismatch. Windows 87-test MSVC suite and Fantasy Zone two-window 2,400-frame acceptance are **NOT TESTED** for this new candidate.
- **Governance:** SHA-pinned cumulative source-only ZIP based on the existing `workspace/v0.4.9.25` commit. `promotion_eligible=false`. Owner's permanent installer `-Mode Validate` is the next gate; application `-Mode Install`, canonical Git commit and immutable `workspace/v0.4.9.27` tag must remain blocked pending full real-ROM acceptance. The 642 protected historical files are not part of this patch.

### Earlier v0.4.9.27 completion candidate — 2026-11-08 (historical notes; Win32 real-ROM acceptance BLOCKED)

- **Owner Windows repair (unvalidated source):** 84/85 CTests passed in transaction `20261108T205941Z-8464`. Only the controller autonomous test failed because native CMake was nested beneath a Windows temporary evidence directory exceeding MAX_PATH (`MSB3491`). Live native compilation now uses short owner-writable per-session `%LOCALAPPDATA%\RecompDev\nb` scratch, keeps SHA-verified translation manifests/diagnostics in the versioned evidence session, and cleans scratch after game exit. Added long-path guard and path-isolation regression; renewed owner MSVC validation and real-ROM gameplay gates remain required.
- Built controller-owned `play ROM --frames 2400`/`run ROM --auto-native`, resolving exact release source staging automatically. No manual job IDs, environment roots or recovery-cycle commands on that path. Existing commands retained.
- The generated native app publishes immutable source/mapper/state-bound gap requests while its gameplay process and presentation objects remain alive; the controller uses verified Ghidra/Rizin analysis, incremental `--module-only` native compilation, verified DLL handoff and same-process resume. The UI pumps while paused. The existing Win32 monitor receives live session/instruction/frame notifications through `ControllerDiagnostics`.
- The CPU Z80 plugin now source-lifts `JP (HL)` using *live register semantics*, not a guessed static address; the translation plugin accepts only CPU-verified supported indirect semantics. No game-specific code or controller-machine coupling.
- Exact ROM, observed mapper/physical code address and controller/CPU/translator/hardware-binary context-keyed compiled DLL cache. Immutable hash-verified entries are committed **only after** all native activations and the requested frame target have completed. Subsequent compatible sessions skip recompiling those modules, while all loader ABI/source/digest checks remain enforced.
- Synthetic Linux single-session **2,400 runtime frames / 2 autonomous DLL activations / same game PID** succeeded. Automated test exercises two autonomous recoveries and first-run MISS/second-run HIT; direct module/hash/ABI and legacy translation regressions remain covered. This does **not** validate real Fantasy Zone, two visible Win32 windows, gameplay parity or release promotion; owner MSVC/Win32 validation is mandatory.
- Existing native module ABI, `run`/`resume`/`preview`, approved tools and 642 frozen historical sources retained. Candidate remains `promotion_eligible:false` until the real-ROM Windows acceptance.

## [workspace/v0.4.9.26] - 2026-11-08 (candidate; Windows acceptance BLOCKED)

- **Owner Windows diagnostic follow-up (source-candidate correction):** Full 82/82 Windows CTests and historical preservation 642/642 passed, but real interactive Shinobi pressed `Z` and stopped at `0x052A`. The automatic preview preflight rejected its own six-member ZIP because `candidate-capture.json` was absent from the verifier allowlist. The bounded verifier now accepts and ROM-identity-checks this known, manifest-hashed optional video-only member alongside `guest-input-cycles.csv`, still rejects unknown members, and emits precise sanitised rejection tokens. Owner runtime recovery and 2,400-frame progress remain **UNVERIFIED**.

- Compiled controller optionally captures live untranslated-code stops and schedules a separate bounded recovery job with the original job/history unmodified. A previously successful neutral frame budget no longer masks fresh input-driven missing code.
- Exact guest-cycle input evidence is source-bound and replayed during the existing native analysis/translation/compile workflow; corrupt, absent or truncated input is rejected.
- Content-addressed store optionally retains partitioned generated native-source files and attested input traces; it is **not** a cache of compiled game DLLs.
- Local Linux native build and focused tests do not prove Windows Win32 monitor behaviour, Shinobi Z-button recovery, cross-ISA runtime or independent game parity. Existing plugin CPU/hardware ABIs unchanged. No Windows runtime activation or release promotion.
- See [release](docs/releases/v0.4.9.26.md), [pre-build scope](docs/project/PREBUILD-v0.4.9.26-AUTONOMOUS-RECOVERY.md), [handover](docs/project/HANDOVER.md).


## [workspace/v0.4.9.25 Windows validation correction] - 2026-11-08

- Fixed the universal artifact store's Windows atomic-publication `ARTIFACT_WRITE_FAILED` caused by an overlong capsule-manifest temporary filename. The immutable content-hash target is unchanged; temporary writes use short same-directory siblings and still commit by rename.
- Original Windows Validate: 80/81 CTests; only `v04925_universal_artifact_store` failed. This corrected candidate requires a fresh full Windows Validate before source promotion. No active runtime change is claimed.

## [workspace/v0.4.9.25] - 2026-11-08

- **Changed:** Add a CPU/hardware-independent, content-addressed C++ artifact store and independently compiled `rd_artifact_store` provider with stable v1 C ABI. Real source-attested analysis and translated C++ source can be promoted into portable, checksum-verified capsules containing their required inputs. The native controller checks capsules first, migrates compatible v23/v24 histories on first execution and persists new recovery artifacts automatically.
- **Validation:** Separate Z80, MIPS and 68000 artifact identities; binary put/get ABI test; source-attested synthetic Ghidra/observed-bank replay after deleting original evidence and relocating the cache; existing job tests, governance and full owner Windows 81-CTest acceptance still required.
- **Compatibility:** No Z80/SMS/68000/MIPS instruction semantics changed. No live hot-loading or compiled game-binary reuse is claimed. Legacy histories remain untouched; old records are migration inputs, not executable trust anchors. Runtime/gameplay parity and state-continuity qualifications remain BLOCKED.


## [workspace/v0.4.9.24] - 2026-11-08 — Shared, source-bound recovery registry and bounded native result ingestion

- **C++ controller recovery registry (new):** Independent `controller/recovery_registry.cpp/.hpp` handles ROM-SHA-keyed, immutable, SHA-verified records pointing to eligible previous recovery sessions under the configured Evidence root. A new `run --rom` automatically selects the highest translated-coverage session from the index or bounded read-only v23/older evidence; `cache --rom` inspects candidate selection; `--no-auto-history` explicitly disables selection; `--import-history` takes precedence. Native provider still checks ROM, source, tools, bank mapper, IR and translated instruction hashes and may invalidate stale history. This is not a compiled DLL cache or checkpoint/replay state.
- **Cross-ROM isolation:** index keyed by full ROM SHA, not game title or logical PC; no SMS/Z80 code in registry, no ROM names hardcoded. Index entries never contain native instruction code, ROM bytes, credentials, or a runtime dispatch pointer. The native controller owns selection and atomic immutable commit; historical job files remain read-only. Tampered indexed artifacts fail closed.
- **RUNTIME-004:** `execution_monitor/native_result.py` separates the 512-KiB stdout *diagnostic* threshold from a 16-MiB hard ingest cap, extracting exactly one bounded valid `NATIVE_APP_RESULT` from a successful native process. 2,400-frame-sized regression with >512 KiB stdout now yields terminal result plus explicit oversize disclosure; absent/duplicated/malformed, unexpected schema or nonzero processes remain rejected. The raw stdout is not truncated or modified; gameplay parity is still not established.
- **Tests and scope:** Two named CTests (`v04924_recovery_registry_contract`, `v04924_native_terminal_result`); controller end-to-end mock confirms automatic reuse without `--import-history`. v0.4.9.23 installed Windows 76/76 and 642 historical hashes, Bank Panic reached 480 frames and Alex Kidd reached 89 (untranslated). **No live in-process hot-loading, code cache of native binary modules, full state checkpoints, deterministic interactive replay or guest parity implemented in this build.** Current source-only track requires owner MSVC 78/78, rollback and cross-ROM acceptance before install.


## [workspace/v0.4.9.23] - 2026-11-08

- **COMPAT-023:** Rizin provider permits the *exact approved* Windows `ESC[2K\r` preamble before an `aflj` JSON array, while preserving the pre-existing newline/warning framing. Standalone carriage returns, unknown ANSI commands, malformed/duplicate/trailing JSON and tool/source/hash mismatch still fail closed. Original logs remain byte-for-byte; audit records the five-byte prefix and normalized function hypotheses separately.
- **Nonblocking, bounded telemetry:** Instrumented game adapters count every watched logical PC hit but emit only first 32 per address plus regular stride-sampled instructions. Periodic (4096-hit) and final audited per-PC/global summaries disclose exact hit totals and intentional coalescing. Finalization occurs in the private compiled preview, not the source-attested translation or active DLLs. A separate, explicit 1-in-16 instruction live-display decimator reduces controller subscriber queue overflow while preserving all source JSONL samples and every input/frame/stop/summary/notice event for display.
- **Fail-closed visibility:** Sample-instruction budget (180,000) reserves remaining event allowance for terminal evidence, emits explicit capture-truncation notice if reached; preview diagnostics distinguish captured sampling, aggregated watch hits, intentionally suppressed UI samples, and actual transport/UI drops. These are different loss domains, not proof of full per-hit archival or reference gameplay parity.
- **Windows and ROM acceptance gates:** New exact-byte provider and telemetry tests supplement 74 existing Windows CTests (target 76). Owner must validate independently with fresh Alex Kidd and Bank Panic jobs; parser acceptance does not prove qualified analyzer function boundaries, compiled game execution or gameplay parity. v0.4.9.22 was installed on local `main` at `9299590078ae5f8af547e2d7733fc428394d83f9` with 74/74 Windows CTests and protected 642/642 unchanged; owner screenshots show running Shinobi native video and live instructions, but telemetry transport losses remain observed. This release is source-only, no active DLLs or historical job mutation.


## [workspace/v0.4.9.22] - 2026-11-08

- **Native monitor responsiveness:** Replace per-batch full-text repaint with bounded reader/UI queues, timer-based (100 ms) Win32 event ingestion, incremental trace rendering and a 2,000-entry searchable history. Report display-transport queue losses without affecting the source evidence log. Terminal PC is identified as terminal rather than conflated with last sampled SP and step count. Win32 watcher token conversion remains proper UTF-8 without lossy wchar narrowing.
- **Monitor filters and capture:** Read-only search, field selector for PC/physical offset/opcode class/event type, matches-only toggle, previous/next navigation and follow-latest. `preview --monitor-pc 0xADDR` and repeatable `--monitor-pc-range A:B` capture watched logical CPU PCs even if `--monitor-every N` would omit them. Each watch event is tagged, bounds are enforced by controller, preview and C++ producer, and game execution is not paused or mutated.
- **Second-ROM acceptance:** Add bounded, sequential `tools/Run-RecompDev-ROM-Smoke.ps1`, producing separate source-attested jobs for each `.sms` file and a per-ROM summary outside Git/AppData. No cross-ROM history import; no ROM contents in diagnostic ZIPs.
- **Windows monitor stress correction:** Initial owner Windows CTest 73/74 exposed a cross-platform test cleanup defect (open telemetry JSONL deleted before publisher closes). The follow-up candidate closes the generic producer stream explicitly and idempotently before inspection/removal, with full Windows suite rerun required. COMPAT-023 (Rizin `ESC[2K` followed by carriage return) remains unfixed and separately tracked.
- **Owner baseline:** v0.4.9.21 installed source commit `87a9ed588e9e155e6a1c7d2fa3132072f60a4603`; all 72 Windows CTests passed with 642 frozen files preserved. Owner screenshots showed the native monitor thread appearing unresponsive until 1,800-frame preview completion; video/input/audio/CPU-state reference parity is still **BLOCKED**. A native process exit 0 is not game correctness. This candidate still requires Windows compilation and visual UI acceptance before source promotion.

## [workspace/v0.4.9.21] - 2026-11-07

- **Native monitor:** Add independent Win32 C++ `RecompDevMonitor.exe` subscribing to the existing authenticated controller diagnostics protocol; current compiled-controller previews stop launching Python/Tk. Python remains a transitional per-preview build/analysis adapter, not a GUI. Original Tk source retained for audit.
- **Frame and parity evidence:** Native generated frontend now reports terminal guest VDP count distinct from host output and last sampled frame. Source-verified preview ZIP can include ordered candidate host-video fingerprints. Native independent `RecompDevParity.exe` compares ROM/input identities and video/audio/state data where supplied, always reporting **gameplay parity unqualified** in the absence of independently attested references.
- **Recovery:** Lift controller/diagnostic/preview session bound from 16 to 128 with bounded immutable history and preserved plateau checks; plugin DLL provenance remains pinned, no automatic upgrade of existing jobs.
- **Owner confirmed before this build:** Local v0.4.9.20 `main` at b3a2db76080899307bea0385aea41648c1b3843a, 69/69 MSVC CTests, original 642 files identical, owner Shinobi completed 1,800 host output frames under compiled native execution (11,794,646 guest steps, no non-neutral input recorded). Input, video/audio timing and gameplay hardware parity remain **BLOCKED**. v0.4.9.21 Windows compiled GUI/entire MSVC acceptance remains owner-run.


## [workspace/v0.4.9.20] - 2026-11-07

- Real v0.4.9.19 owner Shinobi two-window monitor recorded `UNTRANSLATED_INITIAL_CODE` at PC/physical `0xADAF`, 936 host frames and 934 guest counter frames, with no non-neutral input. This is a native guest translation gap, not an observed Z-key crash or proof of gameplay parity.
- New read-only preview ZIP carries an optional exact final mapper/SP/PC/natively observed translation-gap seed and exposes guest-vs-host frame-count domains without silently reconciling them. The GUI marks such a stop `Guest blocked — untranslated instruction` and keeps the last evidence visible.
- `RecompDev.exe resume --job ID --max-cycles N --preview-stop ZIP` now explicitly preflights a SHA-verified, source/ROM/job/cycle-bound preview stop and feeds it into the already established native discovery/translation provider and immutable cumulative recovery history. Invalid archives cannot change job state. Old preview ZIPs lacking observed mapper/SP are rejected, never reconstructed by guessing.
- New regression coverage checks valid/forged preview handoffs and cross-cycle preservation. No controller game-specific code, active runtime replacement, GitHub auto-push or qualified 1,800-frame gameplay claim.


## [workspace/v0.4.9.19] — 2026-11-07

- **Implemented:** Separate controller-owned native preview and sampled instruction/keyboard/guest-stop telemetry, rebuilding only a source-attested copy of the previously generated game; independent game/monitor windows and ROM-free diagnostic ZIP beneath the release evidence root. Preview is not recovery or gameplay qualification.
- **Validated locally:** Current C++ controller, native instrumented synthetic execution, controller diagnostics broker, source immutability and privacy/manifest tests; owner Windows full CTest and real Shinobi keypress still required. Preserved original 642 legacy/baseline source files.
- **Governance:** Source-only `infrastructure-source` track; main baseline v0.4.9.18. Existing GPU/CPU/tool plugin boundary remains independent. 936 observed Shinobi frames, not 1,800 parity.

## [workspace/v0.4.9.18] - 2026-11-07

- **Infrastructure source:** All new controller jobs and diagnostic ZIPs use `<evidence-root>/v0.4.9.18/`; current owner configuration `--workspace C:\Projects\RecompDev-Evidence\v0.4.9.17` resolves to the parent evidence root. Existing AppData or previous version folders remain readable without moving, modifying or deleting the originals. `--evidence-root` is the preferred explicit configuration.
- **Recovery:** Reuse unchanged initial Ghidra/Rizin analysis only after a new SHA-256 ROM/tool/provider-file identity check, Ghidra instruction-byte re-attestation, Rizin input verification and deterministic reconciliation. Cache tampering fails closed; different tool or script versions execute fresh analysis. Newly observed source-checked stops are prioritized ahead of older observations, without bypassing the native CPU/mapper translation gates.
- **Diagnostics:** A compact `coverage-diff.json` records per-cycle new translated physical/PC addresses, observed execution frontiers and analysis reuse, without ROM bytes, native binaries or raw analyzer exports. Old jobs can be exported into the current release's evidence root.
- **Release governance:** Allow validated source-only `dev/v0.4.9.18` checkpoint to originate directly from *exact* promoted `main` commit v0.4.9.17. Full Windows MSVC CTests, preserved 642 files and explicit `-Mode Install` still gate Git main/tag promotion, never active runtime activation. Shinobi remains 896/1,800 observed frames with independent semantic/hardware parity BLOCKED.


## [workspace/v0.4.9.17] - 2026-11-07

- **Changed:** First **infrastructure-source-only** promotion track (`git-main-only-no-runtime`) with mandatory independent Windows tests, rollback and explicit separation from the still-unmet Shinobi 1,800-frame gameplay/hardware parity acceptance. Compiled controller 0.4.13 owns configured large-job workspace, old AppData job lookup, automated sanitised diagnostics ZIPs on terminal recovery states and `diagnostics export --job ID`.
- **Migration:** Expanded inventory to 14 legacy subsystem capabilities with accountable owners and exit criteria; added read-only hashed table-count knowledge inventory. This does not claim complete migration of old campaigns, asset export, all 84 legacy tests, or compiled native Ghidra/Rizin ABI.
- **Validation:** New ZIP safety, source-promotion and migration regression tests plus existing full native/Python suites. Windows MSVC full suite and Install result must be supplied by owner; imported-history Shinobi remains 896/1,800 frames with input/VDP/PSG correctness unverified. Runtime activation remains blocked.

## [workspace/v0.4.9.16] - 2026-11-07

- **Changed:** Preserve an independently re-attested cumulative recovery history across controller sessions; allow explicit legacy evidence bootstrap and detect repeated frontiers or stagnation against job-wide best. Controller 0.4.12 and analysis_integration 0.3.1, no native plugin ABI changes or game-specific offsets.
- **Validation:** Three-session synthetic history, tamper rejection and compiled controller imported-history/stagnation regression tests. Previous owner v0.4.9.15 full Windows 60/60 and two-cycle real-ROM test passed but stopped at 64 frames; v0.4.9.14 reached 894 frames. New Windows acceptance pending, parity still blocked.
- **Release:** Single SHA-pinned ZIP with embedded updated installer can create an offline development Git checkpoint after successful candidate validation, without separate bundle distribution or any change to main, active runtime or GitHub. Promotion eligibility remains false.

## [workspace/v0.4.9.15] - 2026-11-07

- Compiled `RecompDev.exe` now owns persistent ROM-bound jobs and automatically chains bounded recovery batches, preserving immutable session evidence and reattesting source bytes before each resume. New `run`, `resume`, `status`, `inspect`, `configure` commands replace repeated hand-written PowerShell orchestration.
- Added controller-level `--logging debug|info|warning|error` with structured JSONL job events, console threshold and durable diagnostics. Existing Ghidra/Rizin batch adapter remains Python temporarily; no new game-specific logic, CPU/plugin ABI changes or legacy source modifications.
- Native compiled job-manager and actual CLI dispatch tests added. Latest owner real v0.4.9.14 resumed Shinobi evidence reached 894 frames, not 1,800-frame parity; installed `main` remains v0.4.9.9. Candidate is not promotion-eligible.

## [workspace/v0.4.9.14] - 2026-11-07

- Maintained headless Ghidra launcher and scripts, byte-bound function verification, and Ghidra/Rizin reconciliation outside frozen history; optional `--resume-from` imports hash-verified prior recovery seeds and bank overlays into a fresh run. No new native CPU/console semantics or compiled provider ABI.
- Windows real v0.4.9.13 recovered 244 Rizin hypotheses with no legacy Rizin execution but reached a four-round recovery limit at 67 frames; previous main remains v0.4.9.9, validation candidate not production installed.

## [workspace/v0.4.9.13] - 2026-11-07

- Replaced active legacy Rizin `_attempt_rizin` and external-tool authorization imports with maintained, bounded direct provider; kept raw output and provider audit immutable.
- Allowed the Windows Rizin 0.9.1 standalone `ESC[2K` formatting prefix while preserving strict warning/output validation and function hypothesis semantics.
- Added direct-provider/ANSI regression tests and an offline Git development checkpoint plan; compiled controller and plugin versions unchanged. Real Ghidra/Rizin+gameplay acceptance and live installation remain blocked.


## [workspace/v0.4.9.12] - 2026-11-07

- **Controller-owned Rizin compatibility candidate:** Added strict warning-prefixed Rizin `aflj` parsing at the active analysis-provider boundary. The preserved raw analyzer log remains unchanged, JSON normalization is separately SHA-256 recorded, and diagnostic warnings remain visible to the orchestration manifest. Failed or ambiguous outputs still block native translation.
- **Architecture and tests:** Source-only `analysis_integration` advances 0.1.0 to 0.1.1; synthetic analyzer fixtures feed warnings through the compiled controller path, and new provider-level tests cover malformed/error/size/semantics and immutable evidence. No change to controller EXE, native DLLs, translation logic, or frozen 642 historical files. The Rizin/Ghidra subprocess adapters and recovery Python bridge are still temporary historical dependencies, with explicit staged removal gates in the [legacy exit plan](docs/architecture/LEGACY-EXIT-PLAN.md).
- **Release:** Validation candidate based on installed workspace/v0.4.9.9; owner Windows MSVC and real Rizin/Ghidra retry, Shinobi 1,800 frames, second real ROM and full interchangeability remain **BLOCKED**. No automatic tag or active install.


## [workspace/v0.4.9.11] - 2026-11-07

- **Architecture integration, validation-only:** Compiled `RecompDev.exe --stage native-orchestrate` now drives independently authorized Ghidra headless Z80 export and Rizin `aflj` hypothesis analysis via controller-owned compatibility adapters, source-byte/hash reconciliation, native C++ discovery and P-code translation, CMake build, and bounded automatic app-run gap recovery with immutable per-round evidence. Approved Ghidra backends are re-invoked at actual missing-code PCs with verified observed mapper windows to recover reachable function regions as source-hashed, bank-qualified Ghidra P-code overlays. It reuses historical Ghidra preparation and Rizin coordinator *for analysis only*, never the old monolithic production execution or generated runtime. The current compiled execution backend remains SMS/Z80 and fails closed for unsupported platforms.
- **Native evidence contract:** Continuous app now reports observed stopped guest SP and source length; its exact status, mapper and physical offset are reverified by the native mapper and CPU plugins. Rizin only contributes source-checked initial-bank function-entry hypotheses, never executable C++ or independent hardware semantics. The build refuses unapproved analyzer tool paths, unverified ROM exports, repeated gaps and exhausted round budgets.
- **Validation:** Local Linux compiled controller and new provider integration regression pass with two unrelated synthetic ROMs, mock external analyzer processes, real source-based native C++ translation, generated native application build and observed-state execution, and forgery/authorization gates. Real installed Ghidra/Rizin MSVC runs, second *real* ROM, true fully autonomous 1,800-frame parity, universal CPU/machine negotiation and interface isolation remain **BLOCKED**. Original installed workspace v0.4.9.9 and 642 frozen `legacy/` + `baselines/` files are unchanged. This is **NOT** a promotion candidate.


## [workspace/v0.4.9.10] - 2026-11-06

- **2026-11-07 WindowsFix4 (candidate):** WindowsFix3 52/52 owner CTests, then true pilot stopped at `0xB2EE` / 1,590,262 steps (33 steps beyond prior `0xB2E1`) with `ED B0` (`LDIR`) source bytes. `rd_cpu_z80` 0.5.1 adds generic attested LDIR/LDDR one-iteration native C++ execution/repeat branching; new synthetic compiled-DLL fixture validates source-to-RAM three-byte copies in both directions, final guest registers and 21/16 T-state timing. Real Windows full-ROM execution beyond this second stop is NOT YET demonstrated. Frozen history, production DLL boundaries, permanent release installer and installed v0.4.9.9 unchanged; promotion remains blocked.


- **2026-11-07 WindowsFix3 source-recovery correction (candidate):** Owner WindowsFix2 recompiled Shinobi under the independent SMS/video/host DLLs and confirmed 120-frame deterministic parity, then the 1,800-frame neutral-input test stopped at 248 frames / 1,590,229 native steps, guest PC/physical ROM `0xB2E1`, mapper `[0,0,1,2]`, status `UNTRANSLATED_INITIAL_CODE`. The native-pilot recovery now propagates its **observed** stack pointer to source discovery, allowing the CPU DLL to follow CALL/PUSH/RET without guessing mapper safety. Z80 DLL also retains bank context across verified relative/conditional jumps and flags-only operations, and emits source-attested JR NZ/Z/NC/C native code. A generic synthetic call/stack/JR regression covers both observed-SP success and unknown-SP conservative rejection. Real-ROM local source discovery grows from 620 initial candidates to 2,464 candidates with a test-only observed stop seed; these are discovery candidates, **not** 2,464 independently executed instructions. WindowsFix3 still requires Windows MSVC and fresh real-ROM native execution tests. No original source, runtime-state DLL or permanent installer changes; installed baseline v0.4.9.9 untouched.

- **2026-11-07 WindowsFix2 generated-project correction:** The full-ROM generated translation uses a separate 24-partition static library; unlike executable source targets it lacked the maintained `runtime_sms/include` directory and Windows MSVC failed C1083 on `runtime.hpp`. The translator now attaches the active runtime include roots directly to `rd_generated_translation`. Expanded the 600-instruction partition regression to CMake-build/link both generated executables. The prior Windows 52/52 release validation passed; the fresh real Shinobi native project did not compile. Fix remains candidate-only and has not passed Windows yet.

- **2026-11-07 Windows candidate correction:** MSVC C2487 in exported SMS runtime class fixed by replacing static constexpr data members with typed enum constants of identical values. Added portable ABI-header regression guard. Validate-only; no runtime activation, gameplay parity still unverified.

- **2026-11-07 cutover revision (candidate):** Introduced independent `rd_sms_native_runtime` 0.1.0, updated `rd_machine_sms` 0.4.0, `RecompDev.exe` 0.4.9, `rd_translation_pcode` 0.3.0, `rd_runtime_host` 0.1.1. Generated native applications now build and link active SMS state, Mode-4 renderer and generic audio/window/input DLLs from maintained source without compiling original frozen runtime code. The real-Shinobi 120-frame / red-title evidence precedes this cutover and **must be re-proven** under it; still BLOCKED, not tagged/installed. Existing original-source differential reference tests retained; Python analysis/recovery and portable machine-neutral State ABI not finished. New 2 compiled-boundary CTests plus existing regressions.


- **Updated native decoder/translator candidate:** CPU DLL 0.5.0 adds source-attested ED block port I/O, CB BIT/RES/SET, conditional RET, mapper-conservative abstract effects and declared Z80 interrupt vectors. Translator DLL 0.2.0 now preserves source-verified returns and uses stable physical-address C++ partitions for incremental builds. Controller 0.4.8 accepts repeatable, validated native runtime-stop evidence as discovery seeds with no Python decoder or Shinobi-specific instruction patches.
- **Real Shinobi ROM evidence:** SHA-256-matched uploaded 256 KiB source; generated full-nativepilot build executed **338,531 native steps / 64 elapsed frames**, with 3,168 VRAM and 32 CRAM writes; still stopped at untranslated PC `0x53A3`. The particular imported historical bank-export set and current CPU discovery yielded 4,843 emitted instructions and zero rejections; this is **not** proof of graphics, input control or historical 1,800-frame parity. The original Ghidra base export was replaced in the local test by a synthetic empty shell; genuine Ghidra base export and second-ROM parity remain mandatory. Revised candidate is NOT installed or tagged. Evidence now defaults under the release version root, no extra `workspace/` directory. Permanent Git-controlled installer unchanged.

- **Compiled native P-code translation is now real C++ DLL functionality:** `rd_translation_pcode` 0.1.0 accepts source-attested preserved Ghidra export JSON, verifies ROM/source bytes, lowers supported P-code to C++, and builds either the original full nativepilot executable/runtime or an interchangeable source-specific game DLL. The new compiled `RecompDev.exe` 0.4.7 `--stage native-translate` invokes the DLL and CMake without a Python generator or controller wrapper.
- The generated full nativepilot fixture executes with the **same CPU/banking/timing/stop results** as the untouched historical Python generator; a separate generated game DLL executes three native instructions with zero interpreter fallback. Includes strict provenance failures, reuse of original verified `bank-functions.json`, source-id checks, and optional version-scoped evidence output. Generic controller and DLLs have no Shinobi address/title rules.
- **Blocked for real-game parity:** no Shinobi ROM or owner's complete historical base P-code export in build environment; 1,800-frame execution, exact legacy feature parity, automated Ghidra analysis and recovery have **not** been established. Full preserved old workflow remains available. Linux native CTests 45/45 executable tests (two external-archive tests unavailable here); Windows owner compilation still pending. See [release](docs/releases/v0.4.9.10.md) and [approved-scope build record](docs/project/PREBUILD-v0.4.9.10.md).

## [workspace/v0.4.9.9] - 2026-11-06

- **Ported existing native execution orchestration** from the previously verified harness into compiled `RecompDev.exe` 0.4.6. The controller uses a shared compiled game-runner module to load existing P-code-generated game, machine, CPU, discovery, display, audio and input DLLs. New stage `native-execute` refuses source mismatches and runs without Python.
- `rd_cpu_z80` 0.4.0 now structurally recognises documented ED, CB, DD/FD and indexed bytes; `rd_machine_sms` 0.3.0 uses immutable legacy initial mapper values plus source-qualified writes to resolve distinct physical ROM banks. Generic synthetic test exercises `ED 56`, bank 6 and a banked call.
- Updated the workspace-governance regression fixtures to follow current component versions instead of stale v0.4.9.8 expectations; `workspace_governance` v0.1.6.
- **NOT a completed port:** original P-code generator / Ghidra recovery remains Python-hosted; real Shinobi recompile or playability not proven. No changes to frozen original sources, existing Shinobi video/input/monitor or the permanent release process. Owner Windows tests pending. See [v0.4.9.9](docs/releases/v0.4.9.9.md) and [scope record](docs/project/PREBUILD-v0.4.9.9.md).

## [workspace/v0.4.9.8] - 2026-11-06

- **Installable native-discovery release; owner installation pending:** Repackages all uninstalled v0.4.9.7 native controller (0.4.5) and format/CPU/machine DLL source changes on verified owner v0.4.9.6 baseline. No claim that v0.4.9.7 was installed or that newly discovered Master System code has passed the full preserved P-code translator and native compilation gate.
- Introduces one permanent Git-managed `Install-RecompDev-Release.ps1` v1.0.0 to consume independently SHA-256-pinned source ZIPs, validate committed Git blob bytes, stage/compile/test externally, and conditionally commit, tag, back up and activate binaries only after acceptance. First candidate run uses a one-time matching Downloads bootstrap; future accepted releases reuse the root script.
- Documents permanent release process, owner-approved prebuild amendment, scoped protections, native discovery continuity and unresolved Shinobi input/scroll and untranslated-code issues. No frozen historical file or active runtime is replaced by candidate validation; Install mode alone can activate binaries after all checks.

- Windows owner Validate-mode on 2026-11-06 passed 45/45 CTests, 21/21 workspace tests, 10/10 discovery tests, 6/6 installer source checks, documentation governance, and 642/642 frozen-source verification. Native discovery components compiled with MSVC.
- **Owner-directed release-scope amendment:** promote only implemented native discovery and Git-controlled release infrastructure. The outstanding real-ROM -> preserved P-code -> native game build remains the next engineering milestone, not a v0.4.9.8 installation acceptance gate. Install mode must create a commit, tag, bundle and active-binary lockfile before reporting success; earlier Validate runs did not.
- Release installer follows canonical runtime component IDs (`controller`, not executable basename) and verifies Git tag, clean checkout and locked activated DLL hashes after installation.

## [workspace/v0.4.9.7] - 2026-11-05

- **CANDIDATE / NOT INSTALLED:** Compiled controller `0.4.5` now executes structural `--stage discover` via native DLL provider ABI; no Python discovery subprocess. Previous historical discovery remains explicitly available as `--stage legacy-discover`.
- Added compiled `rd_format_sms`, `rd_format_md` and `rd_format_ps1` v0.1.0; extended Z80 and SMS compiled plugins with conservative source decode and static bank-mapping interfaces, keeping previous interpreter/bus ABI.
- Added full-file streaming source SHA-256, per-plugin SHA-256, source-byte-attested Z80 instruction/basic-block candidates, unresolved dynamic/banked branch reporting and synthetic cross-platform CTest coverage.
- Enforced the owner-approved [development contract](docs/project/DEVELOPMENT-CONTRACT.md) and preserved its [pre-build report](docs/project/PREBUILD-v0.4.9.7.md). No game-specific modifications or changes to the Shinobi runtime, its earlier monitor/recovery evidence, or 642 protected files.
- **BLOCKED acceptance:** At least one newly identified block from a real Master System ROM must still be source-verified through preserved Ghidra P-code lowering and native compilation; owner Windows tests and deployment hashes also remain unverified. This implementation must not be promoted as an installed release until those requirements pass.

## [workspace/v0.4.9.6] - 2026-11-05

- Introduced `discovery_integration` v0.1.0, a controller-owned read-only discovery evidence bridge using a versioned registry of interchangeable historical structural, catalogue and ISO sector providers. New reports distinguish fresh work from cached unresolved tasks; they do not claim full code extraction, translation or parity.
- Exposed bounded, sector-aware PS-X EXE and TIM candidate validation without altering the preserved discovery implementation; candidate-byte export remains a separate explicit opt-in operation.
- Corrected the legacy PowerShell wrapper to resolve the installed compiled controller and enforced the main changelog title, uniqueness and newest-first release order through `workspace_governance` 0.1.3.
- Left the Shinobi native recovery, monitor, game project and all compiled plugins unchanged. The prior 44/44 Windows v0.4.9.5 regression result and observed guest stops remain the acceptance baseline; see [v0.4.9.6 release](docs/releases/v0.4.9.6.md).
- **WindowsFix1 installer correction:** closed the synthetic catalogue test’s SQLite connection explicitly before temporary-directory cleanup (Windows file-locking regression); no production pipeline or plugin change.

## [workspace/v0.4.9.5] - 2026-11-05

- Added `controller_diagnostics` 0.1.0: single authenticated, CPU-independent controller event subscription service and bounded fanout.
- Added `execution_monitor` 0.1.0: separate read-only desktop viewer and source-staged native execution event publisher; sampled PC/opcode class, SP, frame, input, and stop reports.
- Added `runtime_host_integration` 0.1.0: `-ExecutionMonitor` and `-MonitorEvery`, event evidence, launcher orchestration; compiled controller and host DLL remain unchanged.
- Verified `movement_trace` 0.2.1 uses the original four-argument frame recorder; separately sampled work RAM stays in the state observer. Removed an invalid fifth argument in the provisional v0.4.9.5 bridge, fixed its regression assertion and improved generated-app compiler error reporting for Windows.
- Preserved all 642 frozen historical files and original translated game C++; Windows GUI and gameplay parity still unverified.

## [workspace/v0.4.9.4] — 2026-11-05

- Added generic `state_observer` v0.1.0: read-only bounded, machine-described memory spans, multi-clock metadata and offline candidate-state correlation without game-specific addresses.
- Updated `movement_trace` to v0.2.0 with a replaceable Master System 8 KiB memory adapter; generic runtime staging enables observation but doesn't alter active DLLs or translated guest code.
- Preserved existing controller/scroll/SAT diagnostics, independent components and historical source. This is not a gameplay or movement fix; real Windows evidence remains necessary.
- See [v0.4.9.4](docs/releases/v0.4.9.4.md).

## [workspace/v0.4.9.3] - 2026-11-05

- Added `movement_trace` v0.1.0 as a source-only, opt-in diagnostic component; correlated logical player input, actual guest SMS controller readbacks, VDP scroll registers and raw SAT sprite positions using guest-cycle/frame timestamps. It does not change the keyboard mapping or claim to identify the player sprite.
- Integrated the tracer into external native-project staging and the automatic runtime-host evidence ZIP; `Run-Native-Game.ps1 -MovementTrace` enables it. All active DLLs, protected legacy code, generated translated instructions and the Workbench remain unchanged.
- Tests include staged native compilation and captured trace, strict source-integrity and negative controller mapping cases. **The existing Shinobi movement-direction anomaly and untranslated `0x1E09` are not claimed fixed.** See [v0.4.9.3 release](docs/releases/v0.4.9.3.md).

## [workspace/v0.4.9.2] - 2026-11-05

- Added replaceable production `rd_video_sms_mode4` v0.1.0 dynamic video DLL: implements sprite compositing, palette/priority and timing-boundary diagnostics behind an independent C ABI. The generic controller, runtime host DLL and translated game instructions are not changed.
- Added `sms_video_integration` v0.1.0 staged-generated-project adapter: makes the native game load the SHA-verified active video plugin without modifying preserved legacy `hardware/adapters/sms.hpp`; collects sprite-table activity in automatic evidence. Video DLL runtime selection is independent of the CPU, input and window presentation layers.
- Focused synthetic sprite tests and staging/native-game smoke cover the integration. **Shinobi sprites, native gameplay and hardware parity still require Windows owner validation.** Previous untranslated input path at `0x1E62` remains a separate recovery item. See [v0.4.9.2 release](docs/releases/v0.4.9.2.md).

## [workspace/v0.4.9.1] - 2026-11-05

- Corrected input-driven production native builds on Windows: compile in the short external `RecompDev-Build/native` directory, preserving full toolchain logs and the previous native application interface. Only final generated-game executables are mirrored into the immutable evidence project's expected compatibility location, not the compiler intermediate tree.
- Allowed explicitly provided, source-attested historical recovery exports to seed the isolated coverage cache instead of disabling all history import; the preserved ROM-byte verifier remains authoritative.
- Skipped post-recovery execution after failed compilation, and distinguished a build blocker from an untranslated guest-code stop. The previous Z-button replay still reproduced `0x7BE8`; advancement past that point is **not yet established**.
- Updated `input_recovery` to 0.1.1, `production_translation` to 0.1.1 and `workspace_governance` to 0.1.2; all compiled controller/DLL versions remain unchanged. See [v0.4.9.1 release notes](docs/releases/v0.4.9.1.md).
Workspace release tags describe **validated combinations and documentation state**, not compulsory version increments for every component. Component-specific changes are recorded in `docs/components/<component>/CHANGELOG.md`.

## [workspace/v0.4.9] - 2026-11-05

- Introduced `input_recovery` 0.1.0: source-only, machine-independent input capture and guarded deterministic replay from native game host evidence into the preserved source-verified recovery pipeline. Guest-cycle event captures supersede wall-time-only host observations; old logs are marked ESTIMATED and must reproduce the previous stop before recovery proceeds.
- Added a reusable Windows `Recover-Native-Input.ps1` launcher and versioned upload-ready replay, source-authentication, recovery and comparison reports. The only native compilation during recovery is generated game-code application work; the controller and unchanged DLLs retain their versions and binaries.
- Added targeted tests for ROM mismatch, malformed input, replay divergence and generated game-code byte-preservation. **Real Shinobi first-level gameplay is not yet established.** See [v0.4.9 details](docs/releases/v0.4.9.md).

## [workspace/v0.4.8] - 2026-11-05

- Added independently compiled `rd_runtime_host` v0.1.0 with a stable CPU-neutral C ABI for BGRA frames, PCM16 samples, input state and window lifecycle; reuse the previously implemented Win32 window and speaker presentation under a reusable shared library.
- Added an optional generated-project presentation bridge and native runtime launcher. It stages previously source-attested native C++ code in the external cache, rebuilds only its native application target and displays actual generated frames through the generic host; the original generated project, ROM and historical evidence remain unchanged.
- Added generic headless ABI, generated-code integrity and wrong-ROM refusal tests. No change to controller, Z80, legacy translator, game-code DLL or machine plugin versions. **ROM independence, interactive Shinobi gameplay and hardware parity are not established.**
- See [v0.4.8 details](docs/releases/v0.4.8.md).

## [workspace/v0.4.7] — 2026-11-04

- Added the separately versioned `production_translation` 0.1.0 hash-verified adapter to the complete original native P-code generator and real reset/replay recovery runner, with explicit original-entrypoint fallback and per-round provenance.
- Restored `workbench` 0.1.0 as an independent, localhost-only, read-only SQLite catalogue viewer, with secure fixed browsing endpoints and external logs.
- No C++ controller or DLL rebuild, no changes to frozen legacy source or owner SQLite catalogue. The full earlier Shinobi 600-frame result is a required regression target, not yet established as parity under this release.
- See [v0.4.7 details](docs/releases/v0.4.7.md).

## [workspace/v0.4.6] - 2026-11-04

- Integrated an independently versioned Z80 source-instruction admission DLL with the actual preservation-backed native recovery workflow. The selected plugin's version, hash and decisions are captured in external run evidence; invalid or rejecting plugins stop recovery before compilation.
- Added a source-only `production_cpu_bridge` component v0.1.0, updated `rd_cpu_z80` to v0.2.0 and versioned workspace governance to v0.1.1. No other compiled DLL or controller version is changed.
- Preserved the original legacy native generator and execution engine; this is source-admission integration, **not** native Z80 translation/execution parity. Added explicit legacy compatibility and strict-required modes.

## [workspace/v0.4.5] — 2026-11-04

### Added
- Authoritative indexed technical documentation covering architecture, each registered component, the real production recovery path, supported platforms, research evidence, developer operations and handovers.
- Mandatory documentation/release-note checks in the Git workspace release and plugin acceptance flow.
- Independently versioned `workspace_governance` tooling component, initial version `0.1.0`.
- Transactional, source-only documentation update procedure with SHA-256 preconditions, historical preservation checks and rollback before commit.

### Changed
- Moved active root-level historical release/validation documents into `docs/history/` and `docs/releases/`, retaining the content and Git history. Protected historical baseline trees are not reorganised.
- Plugin acceptance now requires a meaningful matching component changelog entry before its source change can be committed or activated.

### Unchanged
- Compiled controller `0.4.4`, all ten C++ DLL component versions `0.1.0`, all four legacy service versions `0.4.0.45` and their deployed binaries.
- Production native recovery path, owner catalogue, existing evidence, CMake build outputs and runtime binaries.

### Validation scope
- Documentation structure, link and changelog gates; preserved 642-source inventory; existing CTest suite from already compiled v0.4.4 binaries. Real-ROM execution is not a new qualification in this documentation release.

See [v0.4.5 detailed release notes](docs/releases/v0.4.5.md).

## [workspace/v0.4.4] — 2026-11-04

- Established local Git-managed `RecompDev` source checkout and external build, cache, data, runtime, evidence and archive roots.
- Independently versioned C++ plugin DLL deployment/rollback; local tag and Git bundle. Windows installation, 38 CTest regressions and an isolated Z80 DLL rebuild were reported successful.
- The ten C++ DLLs remained harness-scoped; production discovery/Ghidra/recovery remained implemented by the preserved legacy service adapters.

See [v0.4.4 migration notes](docs/history/v0.4.4/WORKSPACE-v0.4.4.md). Earlier source reports appear under [historical release material](docs/history/README.md).


### v0.4.9.27 AutonomousLive Windows validation correction (source-only)

- Owner first MSVC validation of completion candidate: **83/85 CTests**, `VALIDATE` failed; 642 original historical files preserved, active runtime unchanged.
- Corrected the stale v0.4.9.26 version assertion in `v04915_compiled_job_cli_dispatch`.
- Serialized the heavyweight autonomous live-regression test and added bounded subcommand-log diagnostics to expose the precise Windows failure previously hidden by temporary evidence cleanup.
- **Still blocked:** `v04927_controller_autonomous_two_hot_recoveries` failed initial native translation on Windows; its actual cause has not been established. Not promoted, not installed, no Fantasy Zone 2,400-frame acceptance claimed.
