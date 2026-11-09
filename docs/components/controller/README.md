## v0.4.9.25 — automatic portable artifact retention

The compiled controller (`production-entrypoint`) now uses the independent `rd_artifact_store` source and ABI provider recorded in `workspace/components.json`. `run --rom` selects a verified capsule from a persistent user-scoped store before consulting the legacy history index; on a legacy hit, it promotes complete source-attested analysis/observed-bank inputs into content-addressed objects. `cache --rom` distinguishes portable capsule from old session references. Automatic session publication never modifies historic evidence. Current native translation and replay still reattest ROM, provider, tools and mapper; generated native applications are not yet retained as loadable DLLs and interactive state is not resumed.

## v0.4.9.16 — cumulative persisted job capabilities

**v0.4.9.24 controller-owned recovery registry:** `run --rom` auto-locates a source-matching history session under `RecompDev-Evidence/translation-registry/v1/<rom-sha256>/` or via bounded read-only discovery of earlier versioned job evidence. This registry holds only immutable, SHA-attested history pointers; the existing provider rechecks full source/tool/IR/banked evidence before allowing any reuse. `cache --rom` is inspection-only, `--import-history` overrides selection, and `--no-auto-history` disables it. No manual JSON/log selection for common reruns, no game-specific controller logic. This is NOT a reusable compiled native DLL cache or live stateful continuation; checkpoints and hot-loadable native blocks remain future work.


**v0.4.9.23 current contract:** compiled controller `0.4.19` routes independent versioned new jobs; no active-runtime swap, no Shinobi- or Z80-specific policy. See [v23 release](../../releases/v0.4.9.23.md).

Controller 0.4.12 accepts `run --import-history PREVIOUS_RUN_DIR` to bootstrap a source-matched prior recovery (for example the owner's 894-frame v0.4.9.14 evidence), persists the selection and automatically re-attests it. Every later session uses cumulative copied evidence, and global high-watermark/repeated-frontier stagnation guards stop futile replays. Source and plugin ABIs remain immutable, and Python analyzer batch remains a temporary bridge. See [release](../../releases/v0.4.9.16.md).

# controller — component contract

**Status:** production-entrypoint; documented inventory 2026-11-04. The current version is authoritative in `workspace/components.json` and the component changelog.

## Responsibility

Compiled command entry point; discovers independently versioned native plugins, owns durable job admission and multi-session bounded recovery scheduling with source SHA-256 rechecks and controller-stamped JSONL events. Uses maintained Ghidra/Rizin Python analysis providers **for one batch only** as a temporary compatibility path; legacy workspace commands still available.

## Source and interface

`controller/main.cpp`, `controller/native_job.cpp`, `controller/native_job.hpp`; temporary single-batch `analysis_integration/cli.py`. **Build target:** `RecompDev`. Component kind: `controller`. The registry in `workspace/components.json` is authoritative for version and deployment scope; C++ DLLs export the versioned `rd_get_plugin_v1` interface declared in `harness/include/rd_plugin.h`.

## Qualification and known limits

Not a replacement for individual native recovery services; changing controller governance code does not imply a new compiled EXE. Baseline tests: `v042_compiled_controller_version; v042_compiled_controller_registry; v042_compiled_controller_e2e`. These tests certify only their documented fixtures, not untested real-game CPU/graphics/audio parity.

## Lifecycle

Edit only owned source; bump **this** component if its implementation changes, append a meaningful entry to [its changelog](CHANGELOG.md), run the relevant gates, and accept through local Git. Tooling/services that are not compiled DLLs have no binary to activate. For the generic development rules see [release process](../../development/RELEASE-PROCESS.md).

## v0.4.9.7 candidate interface (0.4.5)

Native C++ `--stage discover` plugin loading and report generation; legacy discovery available via an explicit compatibility stage. The authoritative registry is `workspace/components.json`; use the ABI declarations in `harness/include/rd_native_discovery_v1.h`. Changed native controller and added a strict, versioned format discovery ABI; existing Python prepare/recover workflow remains transitional. No Shinobi-specific logic is introduced; independently measured gameplay parity remains unverified.

## v0.4.6 native migration (workspace/v0.4.9.9)

Shared compiled native game runner moved into controller; executes preserved P-code game DLL with strict full-source identity and no Python execution for native-execute. Existing prepare/recover remain transitional. See [the release](../../releases/v0.4.9.9.md) for what still uses Python and for test limitations. No title-specific workarounds or production gameplay-parity claim.

## v0.4.7 compiled native P-code translation (workspace/v0.4.9.10)

`--stage native-translate` uses `controller/native_translate.cpp` to load independent [rd_translation_pcode](../rd_translation_pcode/README.md), verify original ROM identity and SHA-256-bound Ghidra export instructions, and produce/compile native game C++ without invoking the historical Python generator. The full preserved nativepilot runtime can be compiled, as can a newly generated game DLL for `--stage native-execute`. Existing `--stage recover` still uses the original protected recovery engine; neither autonomous Ghidra analysis nor the historic Shinobi frame budget has been migrated or proven. Its owner-specific real-ROM evidence is required before claiming functional parity. See the [v0.4.9.10 release](../../releases/v0.4.9.10.md).

## v0.4.9.10 maintained-runtime cutover (0.4.9)

The newly generated full native project uses `runtime_sms/templates` and its CMake build links independent SMS state/video/host DLL targets. It **does not** compile or copy the frozen original runtime. This is a source dependency migration, not evidence of equivalent 1,800-frame Shinobi graphics, control or generic machine-ABI parity; verification remains blocked. See [runtime component](../rd_sms_native_runtime/README.md) and [candidate release](../../releases/v0.4.9.10.md).

For v0.4.9.11, `--stage native-orchestrate` requests historical Ghidra/Rizin analysis through [analysis_integration](../analysis_integration/README.md), then keeps native source discovery, translation and generated execution on the maintained compiled controller/DLL path. Rizin candidate entries are never executable provenance; the loop is bounded and requires new verified coverage on retries. Current SMS/Z80 specialisation and Python adapter are migration limitations.

## v0.4.9.15 native workflow CLI (development candidate)

All operations below use **the v0.4.9.15 compiled `RecompDev.exe`**, not the installed v0.4.9.9 binary. One-time configuration explicitly records approved tool paths; configuration is not a tool-downloader or unrestricted search. Windows PowerShell examples are single lines:

```powershell
& "C:\Projects\RecompDev-Build\release-transactions\<TX>\cmake\bin\Release\RecompDev.exe" configure --ghidra "C:\Projects\_Old\Tools\Ghidra-12.2\support\analyzeHeadless.bat" --rizin "C:\Program Files\Rizin\bin\rizin.exe"
& "C:\Projects\RecompDev-Build\release-transactions\<TX>\cmake\bin\Release\RecompDev.exe" run --rom "C:\roms\MASTERSYSTEM\Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms" --logging info
& "C:\Projects\RecompDev-Build\release-transactions\<TX>\cmake\bin\Release\RecompDev.exe" resume --logging debug
& "C:\Projects\RecompDev-Build\release-transactions\<TX>\cmake\bin\Release\RecompDev.exe" status
& "C:\Projects\RecompDev-Build\release-transactions\<TX>\cmake\bin\Release\RecompDev.exe" inspect
```

The `<TX>` placeholder denotes the actual Windows validation transaction ID; the active installed binary does not yet support these commands. Use a candidate path from a successful Windows `Validate` result. The compiled controller resolves its own source-root pointer and plugin DLL directory. Jobs default to `%LOCALAPPDATA%\RecompDev\jobs` on Windows (`RECOMPDEV_HOME` overrides for tests). Every job records source SHA, configured approved tools, strict quotas and an `events.jsonl` stream; the `last-job.txt` pointer is validated and `resume` can be restricted with `--job ID`. The original `orchestration.json` is preserved inside each immutable `sessions/cycle-NN` directory. The provider's prior-output importer rechecks all mapper, instruction hashes and ROM identity before use.

Default `--logging info`; levels `debug|info|warning|error`. Console filtering is not a validation policy and never discards analyzer evidence. Controller events are centralized; CPU instruction-level tracing and cross-process plugin event streaming still need the future compiled diagnostics ABI. Default per-job cap: 8 sessions, 4 analysis rounds per session, 1,800 frames target; `--max-cycles` can increase only within 16 and cannot silently reduce an existing job limit. A stopped process, unexpected evidence or unrecognized status fails closed. This is **not** a proof of semantic parity or execution without the original ROM.

## v0.4.9.17 additions

Use `configure --workspace ABSOLUTE` to keep large job records in a separate workspace; the config and last job ID remain in AppData, with read-only compatibility access to legacy AppData jobs. A compiled `diagnostics export [--job ID]` invokes the versioned bounded maintained Python exporter; recovery-limit/blocked job outputs automatically try to package a redacted upload ZIP. This does not modify source-attested job evidence, implement full game parity or add title-specific CPU logic.

## v0.4.9.18 versioned evidence workspace

`configure --evidence-root ABSOLUTE` stores only lightweight configuration under AppData. Jobs and diagnostics are now created under `ABSOLUTE/v0.4.9.18/{jobs,diagnostics}`. Existing owner `--workspace C:\Projects\RecompDev-Evidence\v0.4.9.17` is recognised as a prior release directory: the parent becomes the root and the next release directory is chosen automatically. New diagnostic exports always target the current release's diagnostics folder, even when locating an immutable old AppData or v0.4.9.17 job. Do not delete old job directories or assume a ROM-free bundle can restore native execution state.

## v0.4.9.19 compiled controller preview

`RecompDev.exe preview --job JOB_ID [--cycle N] [--monitor-every 128] [--frames 1200] [--steps 12000000] [--video window|capture] [--input live|neutral] [--no-viewer] [--hold-window]` resolves a completed/paused job from the configured evidence root, older version directories or the former AppData jobs. The generic controller **does not implement a Z80 disassembler or video path**; it dispatches `execution_monitor/job_preview.py`, a maintained temporary Python adapter. The preview verifies the original source SHA, uses the latest matching compiled native translation, copies only bounded native generated source into `v0.4.9.19/preview`, instruments the disposable CPU-adapter copy and rebuilds a separate executable. Source-attested recovery sessions and active DLLs are immutable. GUI telemetry uses controller-owned authenticated localhost subscriptions; a viewer cannot alter guest execution. A new ROM-free diagnostic ZIP is written under `v0.4.9.19/diagnostics`, with last input mask, stop PC and physical ROM offset. The ZIP **cannot** prove that a key triggered an execution stop; absence of a Z press in an already completed capture is not a runtime crash. The Windows interactive GUI still needs acceptance.

## v0.4.9.20 explicit preview-to-recovery handoff

`RecompDev.exe resume --job JOB_ID --max-cycles NEW_LIMIT --preview-stop FULL_PATH_TO_ZIP` accepts only complete, independently rechecked preview evidence corresponding to the job's immediately previous cycle. An initial read-only preflight refuses invalid/mismatched archives before changing the job; accepted evidence is handed to the existing native analysis-discovery plugin boundary and carried forward as source-verified history. `preview` remains read-only, so users can inspect games without progressing recovery. RecompDev's source promotion still never installs unqualified production binaries.

## v0.4.9.21 bounded automatic recovery

Compiled controller accepts `--max-cycles 1..128` for new source-verified jobs, preserving immutable cycle reports, source checks, existing stagnation policies and pinned DLL identity. Use `--import-history` into a new job to move from a previous release binary; do not silently upgrade old job plugin DLLs. Native preview explicitly selects a standalone `RecompDevMonitor.exe` in the compiled controller build directory; a Python/Tk monitor is no longer launched from this path. Linux headless tests use `--no-viewer`.

## v0.4.9.22 address-targeted preview controls

`RecompDev.exe preview --job JOB_ID --cycle 1 --monitor-pc 0x0BDB --monitor-pc-range 0x0BD8:0x0BE4 --monitor-matched-only` forwards CPU-neutral logical-PC watch filters into the private native capture worker and initial native viewer presentation. Existing `--monitor-every` remains the regular sampling stride; explicit watch matches are emitted even when stride sampling would otherwise skip them. Every option is read-only and does not alter guest instruction execution, recovery jobs, source ROM or production DLLs. These are neither debugger breakpoints nor automatic stepping commands.

## v0.4.9.27 controller-owned live native session

`RecompDev play "ROM.sms" --frames 2400` is a single owner-facing command selecting the approved format/CPU plugin, performing initial Ghidra/Rizin source analysis, compiling native code, starting the Win32 monitor and native game, and handling source/mapper-verified missing-code requests by compiling and loading additional native DLLs in the **same guest process**. The staged controller locates its matching release source automatically. Compiled recovery modules are cached only against verified exact ROM, mapper and binary identities. Unverified instructions, missing tools, corrupt modules and repeated frontiers fail closed. The original `run --rom`, `resume` and `preview` workflows remain compatible. Synthetic Linux 2,400-frame execution passed; Windows two-window/Fantasy Zone acceptance is pending. See [v27 release](../../releases/v0.4.9.27.md).
