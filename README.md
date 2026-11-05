# RecompDev

**Status:** Active development — native-recompilation toolchain, not gameplay-qualified.

RecompDev develops a reusable, CPU- and system-independent binary-recompilation workflow. It aims to discover and verify instructions in existing game binaries, translate verified code into native C++ and connect interchangeable CPU, machine, rendering, sound and input components. The intended final game should operate without its original ROM; **that outcome has not been demonstrated**.

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
