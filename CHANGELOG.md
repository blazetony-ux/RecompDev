# RecompDev workspace changelog

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

## [workspace/v0.4.6] - 2026-11-04

- Integrated an independently versioned Z80 source-instruction admission DLL with the actual preservation-backed native recovery workflow. The selected plugin's version, hash and decisions are captured in external run evidence; invalid or rejecting plugins stop recovery before compilation.
- Added a source-only `production_cpu_bridge` component v0.1.0, updated `rd_cpu_z80` to v0.2.0 and versioned workspace governance to v0.1.1. No other compiled DLL or controller version is changed.
- Preserved the original legacy native generator and execution engine; this is source-admission integration, **not** native Z80 translation/execution parity. Added explicit legacy compatibility and strict-required modes.
