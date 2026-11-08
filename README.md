**v0.4.9.16 candidate:** source-attested cumulative recovery ledger across autonomous controller sessions; optional `run --import-history DIR` for existing evidence, best-frontier stagnation checks and single-ZIP development checkpoint via a validated package-pinned installer. Not installed or parity-qualified. See [release record](docs/releases/v0.4.9.16.md).

## v0.4.9.24 — automatic recovery-history lookup (source candidate)

`RecompDev.exe run --rom FILE` now looks for ROM-hash-matched, source-attested prior recovery sessions automatically in the controller's persistent Evidence-root registry. `RecompDev.exe cache --rom FILE` shows an eligible history without running analyzers; `--no-auto-history` forces a fresh independent recovery and `--import-history` remains available as an explicit override. Reuse is *source-verified recovered translation history*, not a compiled executable cache or live game-state resume. The Z80 and Master System plugins are unchanged. The native preview collector now extracts a unique, bounded terminal result even when stdout is >512 KiB, retaining explicit oversize evidence. New CTests and Windows gate required. [v24 release notes](docs/releases/v0.4.9.24.md) · [prebuild scope](docs/project/PREBUILD-v0.4.9.24.md).


## v0.4.9.23 source candidate — Rizin compatibility and telemetry reliability

The CPU-neutral analyzer boundary now recognizes approved `ESC[2K\r` Windows Rizin framing (`COMPAT-023`) with strict audit and raw-log preservation; this removes a proven *provider parsing* blocker encountered with Alex Kidd and Bank Panic, not an established CPU/ROM incompatibility. Watched-address hits are counted exactly but display instruction details are bounded and coalesced, with explicit loss-domain summaries. A source-only release with independent 76-test Windows acceptance and separate fresh-ROM acceptance, **not** production-runtime or gameplay parity qualification. See [release record](docs/releases/v0.4.9.23.md), [prebuild](docs/project/PREBUILD-v0.4.9.23.md) and [handover](docs/project/HANDOVER.md).


## v0.4.9.22 — responsive native execution monitor and other-ROM testing

The generic compiled controller now supports CPU-neutral `preview --monitor-pc 0xADDR` and inclusive `--monitor-pc-range 0xSTART:0xEND`. The independently deployed Win32 execution monitor has a bounded reader queue, timer-driven UI, incremental trace, address/opcode/event search, matched-only filter and follow controls. It does not load the ROM, modify guest execution or link Z80/SMS code. `tools/Run-RecompDev-ROM-Smoke.ps1` can run independent bounded acceptance jobs for the owner's Master System ROM folder (Shinobi skipped by default); each receives a separate ROM hash/job/evidence. Reference gameplay parity is not established. The source-only release installer preserves all historical sources and does not activate runtime DLLs.


**v0.4.9.21 candidate:** Native C++ execution monitor, standalone parity-capture comparator, explicit terminal frame accounting and configurable 128-cycle controller recovery. Owner v0.4.9.20 reached 1,800 observed Shinobi frames; gameplay, input, audio, video and emulator parity are **not yet proven**. See [release](docs/releases/v0.4.9.21.md). No production runtime activation.

**Permanent release installer:** `Install-RecompDev-Release.ps1` is Git-managed after first accepted promotion; see [single ZIP release procedure](docs/development/RELEASE-PROCESS.md) and [v0.4.9.8 installable release](docs/releases/v0.4.9.8.md).

**Mandatory development policy:** [Native-first development contract](docs/project/DEVELOPMENT-CONTRACT.md) and [approved v0.4.9.7 pre-build scope](docs/project/PREBUILD-v0.4.9.7.md). Every future build requires owner approval of a report before implementation.

# RecompDev

**Status:** Active development — native-recompilation toolchain, not gameplay-qualified.

RecompDev develops a reusable, CPU- and system-independent binary-recompilation workflow. It aims to discover and verify instructions in existing game binaries, translate verified code into native C++ and connect interchangeable CPU, machine, rendering, sound and input components. The intended final game should operate without its original ROM; **that outcome has not been demonstrated**.

## v0.4.9.10 active native runtime cutover — candidate only

The native translator now builds independent SMS machine-state (`rd_sms_native_runtime`), video (`rd_video_sms_mode4`) and host (`rd_runtime_host`) DLLs from maintained sources. Frozen `legacy/` and `baselines/` are reference-only for this newly generated native build. The previous 120-frame Shinobi image was produced **before** this cutover; graphics/input parity through these new DLLs, original-ROM-free operation and a full controller-managed Ghidra/recovery workflow are not yet proven. [Candidate details](docs/releases/v0.4.9.10.md).

## v0.4.9.15 controller-owned jobs — validation candidate

The newest *development candidate* adds native compiled job lifecycle, bounded automatic source-attested recovery continuation, `--logging debug|info|warning|error`, and `run`, `resume`, `status`, `inspect`, `configure`. The installed baseline remains v0.4.9.9; do not use these commands on the older active binary. See [controller workflow](docs/components/controller/README.md) and [candidate release](docs/releases/v0.4.9.15.md). The per-batch Ghidra/Rizin analysis adapter is still Python pending compiled provider ABI migration; real native parity remains **BLOCKED**.

## Start here

- [Documentation index](docs/README.md) — topical navigation and document status
- [Architecture contract](docs/architecture/ARCHITECTURE-CONTRACT.md) — non-negotiable component boundaries
- [Current handover](docs/project/HANDOVER.md) — confirmed implementation, constraints, next milestone
- [Development workflow](docs/development/WORKSPACE.md) — Git, isolated builds, activation and rollback
- [Release process](docs/development/RELEASE-PROCESS.md) — component changelogs, approval gates and tags
- [Workspace changelog](CHANGELOG.md) — verified workspace changes

## Working layout (Windows defaults)

Source: `C:\Projects\RecompDev` (Git). Sibling directories: `RecompDev-Build`, `RecompDev-Runtime`, `RecompDev-Cache`, `RecompDev-Data`, `RecompDev-Evidence` and `RecompDev-Archive`. Run logs, catalogues, captures and binaries **do not belong in the source checkout**.

Run `& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin status` to view separately versioned components and their true scopes. Native DLL swapping is currently demonstrated in the C++ harness; the real Shinobi recovery workflow still uses preserved Python services. See [production pipeline](docs/recompilation/PRODUCTION-PIPELINE.md).

## Protected historical implementations

Original v0.4.0.45 and modular harness v0.3 sources remain unchanged under `legacy/` and `baselines/`. The source-preservation gate verifies 581 + 61 = **642 files**. The original release ZIPs are stored externally in `RecompDev-Archive/original-archives`. Do not modify those baselines to improve documentation.

## Standalone Workbench (workspace v0.4.7)

The read-only SQLite catalogue browser is independent of RecompDev's compiled controller: `& "C:\Projects\RecompDev\tools\Start-Workbench.ps1"`. It opens a token-protected local page showing tables, schemas and bounded rows from `RecompDev-Data/catalogue.sqlite`, and writes logs only to the external Evidence root. See [Workbench docs](docs/components/workbench/README.md).

Native recovery continues to use the full preserved v0.4.0.45 translation/recovery implementation through a hash-pinned provider; it does not downgrade to the small synthetic Z80 interpreter. See [v0.4.7 release](docs/releases/v0.4.7.md).

### Generic native runtime host (v0.4.8)

`rd_runtime_host` is an independently built presentation DLL for CPU-neutral framebuffers, PCM audio and button events. After activating the host, use `tools/Run-Native-Game.ps1 -Rom <local-ROM>` to stage and run the latest matching previously generated native project. See [runtime host instructions](docs/components/rd_runtime_host/README.md). The native game currently still requires its original ROM; gameplay and independent hardware parity remain unverified.

## v0.4.9.9 native execution integration

The Git-managed native controller now offers `--stage native-execute --rom FILE --game rd_GAME_MODULE --steps N --out EVIDENCE_PREFIX` and directly loads the source-attested original P-code game DLL through a shared compiled C++ runner, not a Python subprocess. The existing C++ `RecompDevHarness` remains a test executable. Both use interchangeable ABI-checked machine, CPU, game, event, input, audio and display plugins. Do not use a synthetic fixture DLL with a different ROM; the source SHA-256 check will reject it.

CPU discovery additionally handles documented Z80 ED/indexed source forms and carries source-qualified SMS mapper state. **This does not yet port the original Python Ghidra/P-code generator or establish real-ROM gameplay parity.** Consult [the current release record](docs/releases/v0.4.9.9.md) and [owner scope/acceptance](docs/project/PREBUILD-v0.4.9.9.md). The same root Git-managed `Install-RecompDev-Release.ps1` is reused unchanged for the next ZIP.

## v0.4.9.10 compiled translation candidate (not installed)

The new `rd_translation_pcode.dll` implements actual C++ P-code-to-native game code emission behind the compiled `RecompDev.exe --stage native-translate` controller, generating either the full preserved nativepilot runtime application or a controller-executable independent game DLL from source-attested Ghidra exports. This goes beyond v0.4.9.9's ability to execute existing generated code. For source requirements, CLI options, status and limitations see [the translation plugin](docs/components/rd_translation_pcode/README.md) and [v0.4.9.10 release record](docs/releases/v0.4.9.10.md). **Real Shinobi historical 1,800-frame parity and second-game cross-check remain unverified; candidate must not be promoted yet.** Use the unchanged permanent Git-managed release installer for validation, no manual copying of ZIP files into the repository.

### v0.4.9.10 ongoing native translation migration

This is a candidate against the installed v0.4.9.9 baseline, not an activated release. Compiled `RecompDev.exe` 0.4.8 plus `rd_cpu_z80` 0.5.0 and `rd_translation_pcode` 0.2.0 now support source-authenticated ED block I/O, CB BIT/RES/SET, conditional return, IM1 source-vector coverage, source-verified observed-runtime-gap recovery seeds and incremental native translation partitions. Real 256 KiB Shinobi ROM testing reached 338,531 native guest instructions and 64 elapsed frames, but no historical 1,800-frame/gameplay parity. `--runtime-gap-report <PILOT_RESULT log or JSON>` can be repeated alongside `--stage native-translate --discover-source` to seed discovery from verified mapper/PC state. Existing Ghidra base exports and other cartridge support remain incomplete. See [v0.4.9.10 release notes](docs/releases/v0.4.9.10.md) and [production pipeline](docs/recompilation/PRODUCTION-PIPELINE.md).

## v0.4.9.11 candidate: Ghidra/Rizin native analysis integration

The compiled `RecompDev.exe --stage native-orchestrate` now coordinates optional explicitly approved local Ghidra and Rizin analysis via a temporary isolated `analysis_integration` provider adapter; it feeds authenticated outputs to maintained native discovery/translation DLLs, compiles an independent native app, and retries genuine missing-code stops within bounded rounds. With an authorized Ghidra executable it re-analyzes the observed bank and stopped PC, then feeds source-verified function regions back into native C++ translation, rather than blindly patching one opcode. It does not use the frozen monolithic recovery engine for production compilation/execution. The initial backend is SMS/Z80 only; real Windows analyzer execution, a second unrelated **real** ROM, 1,800-frame behaviour and graphics/input/audio parity are **not yet validated**. See [v0.4.9.11](docs/releases/v0.4.9.11.md).

**v0.4.9.13 candidate:** maintained direct Rizin provider `analysis_integration 0.2.0`; installed workspace remains v0.4.9.9 until separate owner acceptance and transaction. See [release notes](docs/releases/v0.4.9.13.md) and [legacy-exit plan](docs/architecture/LEGACY-EXIT-PLAN.md).

**v0.4.9.14 candidate:** maintained Ghidra provider and source-attested opt-in recovery evidence reuse; no live install/parity promotion. See [release notes](docs/releases/v0.4.9.14.md).

## v0.4.9.17 infrastructure-source candidate

The compiled `RecompDev.exe` accepts `configure --workspace ABSOLUTE_DIRECTORY` to keep generated job data outside AppData, `diagnostics export --job ID` and automatically packages bounded redacted evidence ZIPs after a terminal recovery result. Existing AppData jobs remain accessible; configuration stays in AppData. Do not share the raw ROM or private Ghidra databases. Review redacted ZIPs before uploading. Runtime ZIP packaging currently uses a maintained Python adapter invoked by the compiled controller; the final native provider ABI remains pending.

The single ZIP's pinned installer separates infrastructure source `main` promotion from gameplay runtime qualification. Passing the complete Windows suite makes **Git source-only** promotion eligible via explicit `-Mode Install`; it does not install EXEs/DLLs or indicate a playable game. The Shinobi 1,800-frame and hardware parity deliverable remains BLOCKED.

**v0.4.9.18 infrastructure candidate:** All new jobs and diagnostic ZIPs now reside in versioned directories under the configured evidence root (including when exporting old AppData jobs); `coverage-diff.json` reports genuine translated-address deltas, and unchanged initial Ghidra/Rizin analysis is reused only after ROM/tool/provider/IR SHA-256 attestation. Run `RecompDev.exe configure --evidence-root C:\Projects\RecompDev-Evidence` to configure the root explicitly; existing owner `--workspace ...\v0.4.9.17` is also recognised. This work remains a source-only release until owner Windows CTests and Git promotion pass; gameplay parity remains blocked.

## v0.4.9.19 native preview (development candidate)

With a Windows-validated, independently built v0.4.9.19 `RecompDev.exe`, `preview --job JOB_ID` starts a disposable source-attested native game window plus the independent read-only live instruction monitor. Original recovery sessions remain immutable; a compact ROM-free diagnostics ZIP goes to `RecompDev-Evidence/v0.4.9.19/diagnostics`. Use `--video capture --input neutral --no-viewer` for CI. The preview does not qualify gameplay or repair untranslated code and is not activated by source-only Git promotion. See [release](docs/releases/v0.4.9.19.md).

## v0.4.9.20 preview-to-recovery handoff (candidate)

After a v0.4.9.20 `preview` emits a complete `recovery-seed.json` in its diagnostics ZIP, resume with `RecompDev.exe resume --job JOB_ID --max-cycles NEW_TOTAL --preview-stop ABSOLUTE_ZIP`. The controller checks ROM, original translated source, job/cycle, mapper and native stop before changing a job. Preview remains a separate, read-only diagnostic execution and cannot itself qualify the game. Owner v19 preview stopped at PC `0xADAF` without keypress; original older ZIP does not contain sufficient state to use as a new native recovery seed. See [v20 release](docs/releases/v0.4.9.20.md).
