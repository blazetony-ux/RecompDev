## v0.4.9.16 — cumulative persisted job capabilities

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
