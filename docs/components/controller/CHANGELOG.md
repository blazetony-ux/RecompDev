# controller — independent changelog

## [0.4.19] - 2026-11-08

- **Changed:** Compiled `RecompDev.exe` and ROM-identified job namespace version advanced to `v0.4.9.23`, preserving controller-to-CPU/machine/plugin boundaries. Python analyzer and preview modules remain separately swappable; no direct game-specific logic, ROM overrides, or pinned-native DLL replacement.
- **Validation:** Controller job lifecycle and CLI dispatch passed focused Linux native CTests; full 76-test MSVC owner acceptance pending, with original 642 protected files unchanged.
- **Compatibility:** Existing v22 jobs are not rewritten or silently migrated; new work uses a separate evidence-root release folder. Non-neutral input and reference gameplay parity remain independently unqualified.


## [0.4.18] - 2026-11-08

- **Changed:** The generic C++ controller now accepts bounded repeatable `--monitor-pc` and `--monitor-pc-range` address watches plus optional `--monitor-matched-only`, safely forwards normalized addresses into the independent native telemetry subscriber and rejects malformed or unsupported command combinations. Versioned evidence root advances to v0.4.9.22; existing v0.4.9.21 jobs remain pinned to their source/build.
- **Validation:** Compiled controller test checks two watch parameters, range normalization, rejection of reversed/out-of-range addresses, no mutation of source-attested jobs, and the existing 20-cycle scheduling regression.
- **Compatibility:** No controller-specific Z80/console instructions, no new CPU/format/machine ABI, no automatic source modifications in previous jobs, no active runtime replacement. Works with existing analyzer provider configuration.

## [0.4.17] - 2026-11-07

- **Changed:** Controller-owned recovery sessions now support up to 128 total cycles per new job with immutable source-checked history and the existing stopping conditions; preview launches only its independent `RecompDevMonitor.exe` subscriber, not Tkinter.
- **Validation:** New native monitor, parity and preview-bounds contracts plus compiled controller job/CLI tests; Windows MSVC native GUI integration requires owner acceptance.
- **Compatibility:** No CPU/machine/translator ABI changes, active runtime updates, old job mutation, game-specific rules or edits to 642 frozen files; v0.4.9.20 job DLLs remain pinned and are not swapped.

## [0.4.16] - 2026-11-07

- **Changed:** Add opt-in `resume --preview-stop ZIP` and independent preflight before changing job metadata; first resumed batch receives a verified preview-bound gap, persisted by the standard history importer.
- **Validation:** C++ job contract verifies accepted/rejected preview dispatch, no writes on invalid evidence, correct original job/round selection; complete owner Windows CTests remain outstanding.
- **Compatibility:** No implicit preview auto-resume and no alteration of old runtime, plugin ABIs, protected historical archives or versioned evidence.

## [0.4.15] - 2026-11-07

- **Changed:** Compiled `RecompDev.exe preview [--job ID]` now resolves old and current source-attested recovery jobs, validates original ROM SHA and dispatches a separate bounded native preview service. New versioned evidence root `v0.4.9.19` captures sessions/diagnostics; preview cannot mutate recovery jobs or active runtime DLLs.
- **Validation:** New C++ compiled job contract exercises correct `job-preview` dispatch, evidence routing, backend bounds, unchanged `job.json`; external native synthetic smoke proves compiled instrumentation, structured guest-stop and SHA-256 diagnostic ZIP. Full owner Windows GUI and Z-key behaviour remain unqualified.
- **Compatibility:** Existing `run/resume/status/inspect/diagnostics export` contracts, source identity, provider DLL ABIs, v0.4.9.18 historical jobs and original frozen 642 files remain unchanged; prior AppData config only stores pointers and settings.

## [0.4.14] - 2026-11-07

- **Changed:** Configured evidence root is independent of historic job location; `v0.4.9.18/jobs` and `v0.4.9.18/diagnostics` are release-scoped. Supports prior version folders and AppData lookup; `configure --evidence-root` overrides legacy `--workspace` while existing owner v0.4.9.17 workspace automatically resolves to parent root.
- **Validation:** Compiled CLI routing smoke includes old version and AppData fixture ZIPs, explicit root setup and path rejection. Full Windows owner CTest and Ghidra/Rizin native gameplay validation pending.
- **Compatibility:** Controller is still C++; Python only handles bounded analyzer/digest orchestration. Original job evidence and active production binaries never rewritten.


## [0.4.13] - 2026-11-07

- **Changed:** The compiled controller accepts `configure --workspace ABSOLUTE`, defaults new large jobs to the sibling `RecompDev-Work` root rather than AppData, keeps configuration/last-job metadata in AppData, and can still inspect or resume older AppData-based jobs without migrating or deleting them. It invokes a bounded, redacting upload ZIP exporter automatically when native recovery terminates and via `diagnostics export --job ID`.
- **Validation:** Existing three-session native controller tests and real compiled CLI smoke, plus new sanitized ZIP adversarial tests covering preserved original files, checksums, path/secret redaction and exclusion of ROM files. Owner Windows MSVC full CTest and authentic tool acceptance still pending.
- **Compatibility:** The bundled packager is a maintained Python analysis/workflow adapter dispatched by compiled controller; not yet an independently loadable C++ diagnostic-provider ABI. No SMS/Z80 or P-code DLL ABI changes, original job folders remain immutable, and no game semantic qualification is claimed.

## [0.4.12] - 2026-11-07

- **Changed:** Persistent native controller `run --import-history PREVIOUS_RUN` starts from a source-matched historical analysis report, then carries verified evidence forward between automatic sessions. Global best frame/emitted high-watermarks and repeated PC/mapper execution-frontier detection prevent misleading adjacent-round progress resets.
- **Validation:** Compiled multi-cycle job contract now rejects forged external source identity, proves the verified initial history path is forwarded to the batch analyzer and detects three-round stagnation against global best. Windows real-tool acceptance is still outstanding.
- **Compatibility:** Native plugin C ABIs, structured logging, original hardware-neutral job lifecycle and source checks remain unchanged. The imported game reports are authenticated by the Python Ghidra/Rizin compatibility provider, not a compiled native analysis ABI.

## [0.4.11] - 2026-11-07

- **Changed:** Compiled C++ controller gains `run`, `resume`, `status`, `inspect` and `configure`; an external user-state job registry with source SHA-256 identity, immutable numbered recovery sessions, bounded automatic cross-session scheduling, stagnation detection and native controller JSONL severity logs (`--logging debug|info|warning|error`). The previous single-batch Python analysis adapter remains temporary; no changes to CPU/machine/translation DLL ABI.
- **Validation:** Native C++ GCC build and synthetic compiled job-manager contract and real executable CLI-dispatch tests cover three automatic sessions, source mutation rejection, path/option bounds, strict terminal state and logging records. Authentic Windows MSVC and second real ROM are outstanding; the owner v0.4.9.14 native Shinobi resume reached 894 frames but parity is not established.
- **Compatibility:** Legacy `--stage native-orchestrate`, `--stage discover`, `--stage native-translate`, C plugin descriptors, source-attestation gates and 642 frozen historical files remain unmodified. The new scheduler does not claim to be an independent compiled Ghidra/Rizin provider ABI or general M68K/MIPS recompilation. Promotion blocked until all acceptance conditions pass.

## [0.4.10] - 2026-11-07

- **Changed:** Added compiled `native-orchestrate` entry point, external Ghidra/Rizin provider request forwarding and source-checked Rizin boundary-seed import into the compiled discovery and translation paths. Bounded automatic recovery is a controller-owned workflow via a temporary isolated Python adapter, not a CPU or machine plugin function.
- **Validation:** Linux native build and a new two-source synthetic integration CTest pass, including deliberately fake external analysis tools, generated C++ build, source mismatch rejection and tool-root authorization; owner Windows real-tool and 1,800-frame test remain blocked.
- **Compatibility:** Existing discover, native-execute and native-translate stages remain; Ghidra P-code remains authoritative and Rizin is non-executable evidence. Installed runtime and original histories are never mutated. Remaining compiled controller Z80/SMS specialisation must be removed in a later provider-ABI milestone.


## [0.4.9] - 2026-11-07

- **2026-11-07 candidate continuation:** Native discovery now preserves an optional 16-bit `sp` from a genuine bounded `PILOT_RESULT` recovery report; the CPU plugin—not the controller—proves stack writes cannot alter SMS ROM-bank registers. Missing SP remains unknown. Existing `--runtime-gap-report` and DLL API are unchanged; the larger `NATIVE_APP_RESULT` schema is not accepted as a native-pilot report.
- **Changed:** The controller now passes the authoritative active source root into generated native CMake projects so regenerated Master System games link maintained `runtime_sms`, video Mode-4 and generic presentation DLLs. No historic `runtime.cpp` or `interactive.cpp` is copied or compiled from frozen source into a new game.
- **Validation:** Linux native controller and synthetic P-code generated executable rebuild and run successfully against the original historical CPU-state reference; the new native runtime ABI and static production-dependency boundary tests pass. Owner Windows DLL linking and Shinobi frame parity remain unverified.
- **Deployment:** Uses the Windows DLL-load-directory search flags so indirect `rd_sms_native_runtime` and `rd_video_sms_mode4` dependencies are resolved from `RecompDev-Runtime\active`. The installed-layout regression now stages these transitive DLLs and explicitly rejects missing/wrong plugins.
- **Compatibility:** Existing `--stage native-translate` and `--stage native-execute` parameters and source hash admission are preserved. The historical Python Ghidra/recovery providers are not newly ported by this update; permanent Git installer and original source history remain unchanged.

## [0.4.8] - 2026-11-06

- **Changed:** Native controller now consumes bounded `PILOT_RESULT` untranslated-code reports as recovery seeds; verifies mapper PC-to-physical ROM offset with `rd_machine_sms.dll`, dispatches the verified bytes to the Z80 discovery DLL, and optionally feeds the resulting source-attested instructions back to the native P-code translation DLL. Multiple reports are supported without game-specific hardcoding. Corrects discovery's version metadata and default evidence root has no extra `workspace` segment.
- **Validation:** Source-only synthetic recovery admits CB BIT/RES and conditional RET, rejects forged physical address / ROM size / status; on the actual owner Shinobi ROM, compiled Linux pilot advanced past startup and serviced IM1 interrupt, reaching 338,531 native instructions and 64 frames. Not full runtime parity, graphics or input acceptance.
- **Compatibility:** Existing plugin ABI, preserved runtime and frozen sources unchanged. Explicit runtime evidence remains optional; automatic multi-round native recovery is not yet integrated.

## [0.4.7] - 2026-11-06

- **Changed:** New compiled `--stage native-translate` directly loads ABI-checked `rd_translation_pcode` C++ DLL, authenticates original source and immutable Ghidra instruction export bytes, orchestrates CMake builds and outputs the full historical nativepilot application or an independent game DLL. Optional historical bank export collection is source-id-verified; no title-specific decoder rules or Python generator subprocess.
- **Validation:** Native C++ compilation, differential full-runtime generated-output execution versus the unmodified historical generator, source mismatch rejection, synthetic banked-recovery export import and independently built game DLL/controller execution passed in available Linux tests. Owner Windows real-ROM Shinobi parity is still unproven.
- **Compatibility:** Existing controller discover/native-execute and preserved Python Ghidra recovery stages remain available; no existing CPU/machine/game descriptor interfaces or frozen original source changed. New translation plugin has an independent versioned C interface and does not claim automated analysis or recovery.

## [0.4.6] - 2026-11-06

- **Changed:** Shared compiled native game runner moved into controller; executes preserved P-code game DLL with strict full-source identity and no Python execution for native-execute. Existing prepare/recover remain transitional.
- **Validation:** Linux C++ compilation and compiled native controller/P-code and generic banked-flow regression, along with existing workspace tests. Full Windows owner validation, real-ROM translation and semantic parity are not yet demonstrated.
- **Compatibility:** C plugin descriptor ABI and existing runtime bus ABI remain unchanged. New optional symbol extensions are loaded by the compiled controller; original history is untouched and all missing/ambiguous execution cases fail closed.

## [0.4.5] - 2026-11-05

- **Changed:** Native C++ `--stage discover` plugin loading and report generation; legacy discovery available via an explicit compatibility stage.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** Changed native controller and added a strict, versioned format discovery ABI; existing Python prepare/recover workflow remains transitional.

This file records only changes to `controller`. Component versioning is independent of workspace release tags.

## [0.4.4] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `controller` controller at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `v042_compiled_controller_version; v042_compiled_controller_registry; v042_compiled_controller_e2e`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `production-entrypoint`. Not a replacement for individual native recovery services; changing controller governance code does not imply a new compiled EXE.
