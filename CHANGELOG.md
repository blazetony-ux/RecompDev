# RecompDev workspace changelog

Workspace release tags describe **validated combinations and documentation state**, not compulsory version increments for every component. Component-specific changes are recorded in `docs/components/<component>/CHANGELOG.md`.

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
