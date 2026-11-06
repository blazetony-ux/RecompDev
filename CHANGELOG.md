# RecompDev workspace changelog

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
