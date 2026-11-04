# RecompDev v0.4.4 — permanent protected workspace

The source location is **`C:\Projects\RecompDev`**. Local Git keeps only source,
version metadata and checked-in fixtures. Generated `.exe`, `.dll`, `.obj`, CMake
files, run logs, caches, evidence and ZIPs belong **outside** the checkout:

| Root | Purpose |
| --- | --- |
| `RecompDev` | Git-tracked C++/Python source, APIs, manifests, tests and documentation |
| `RecompDev-Build` | CMake objects, generated artifacts, build/test logs |
| `RecompDev-Runtime` | Standalone controller, harness, immutable versioned DLL store and active DLLs |
| `RecompDev-Evidence/v0.4.4/<run-id>` | Run logs, captures, SQLite working snapshot, upload ZIP |
| `RecompDev-Cache` | Disposable compilation/recovery cache (not diagnostic evidence) |
| `RecompDev-Data` | Existing owner catalogue; never overwritten or imported into Git |
| `RecompDev-Archive` | Original source ZIPs, immutable previous releases and rollback backups |

`RECOMPDEV_PROJECTS_ROOT` may override the sibling directory base in workspace tools;
`RECOMPDEV_EVIDENCE_ROOT` may override evidence location for the controller.

## One-time install

Run the standalone `Install-RecompDev-Workspace-v0.4.4.ps1` from Downloads.
It refuses to replace an existing `RecompDev` source checkout or overwrite
baseline archives with a different SHA. Existing versioned installations,
evidence and `RecompDev-Data/catalogue.sqlite` are never modified.

The installer verifies the original 642 historical files, creates a **local-only
Git repository**, builds into `RecompDev-Build/cmake`, runs the full CTest suite,
and publishes an independent controller and versioned plugins to the runtime.
It creates an annotated `workspace/v0.4.4` tag only after tests pass and stores
a verified Git bundle in `RecompDev-Archive/git-backups`. It leaves source clean.
Git and the local bundle are **not** an off-drive backup; also back up the
project and external data independently.

## Normal development

```
# Compile just the Z80 DLL; source tree remains unchanged
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action build -Component rd_cpu_z80
# Run only its test selection
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action test -Component rd_cpu_z80
# Raise the version of *only* this component before publishing new bytes
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action bump -Component rd_cpu_z80 -Argument patch
# Version bump is an uncommitted source edit until accepted through Git.
# Verify, build only Z80, test, Git commit, and activate in one step:
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action accept -Component rd_cpu_z80
# Reverse selected runtime binary without recompilation
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action rollback -Component rd_cpu_z80
```

For a small **file-replacement ZIP** created by development, use:

```
& 'C:\Projects\RecompDev\tools\Apply-RecompDev-Update.ps1' -Package 'C:\Users\you\Downloads\RecompDev-Update.zip'
```

It validates expected old and new SHA-256 for every file, checks Git cleanliness,
verifies exactly one component's version changed, patches only listed paths,
builds only the affected CMake target, runs targeted tests, checks historical
integrity, then commits and activates. On build/test failure it restores source;
previous activated binaries remain installed. No blind `git add -A` on updates.

The ordinary **replace file -> bump component -> accept** workflow does not require ZIP creation.
Only the changed component gets a new version.

Small ZIP format:

```
update.json   # {"schema":"recompdev-update-v1","component":"rd_cpu_z80",
              #  "new_version":"0.1.1","files":[{"path":"workspace/components.json",
              #  "old_sha256":"...","new_sha256":"..."}, ...]}
workspace/components.json
harness/plugins/cpu_z80.cpp
```

Release tags are *workspace snapshot identities*, not automatic changes to
unchanged component versions. `workspace/components.json` is authoritative.
An immutable runtime store disallows publishing different DLL bytes under the
same component/version identity.

## Architecture boundary — important

The ten compiled DLL targets are interchangeable **in the C++ harness**.
The real Shinobi/native-recovery workflow still uses the preserved v0.4.0.45
Python service adapters. Publishing `rd_machine_sms.dll` does *not* presently
replace the SMS implementation used by that production recovery service.
The manager marks every component's scope explicitly to prevent a misleading
claim of production interchangeability. Full native CPU/machine/recompiler
service migration is a separate, gated project milestone.

## Preservation exceptions

The verified historical source tree contains an immutable SQLite catalogue
fixture, and the synthetic test suite contains a tiny `.sms` binary fixture.
They are *source fixtures*, not compiled output. Removing them would break the
642-file SHA inventory and original source-byte validation. Original archive
ZIP files are moved into `RecompDev-Archive/original-archives`; no generated
binary artifacts or logs are placed in the Git source checkout.

## Verification

```
git -C C:\Projects\RecompDev status --short
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action status
& 'C:\Projects\RecompDev\tools\RecompDev-Workspace.ps1' -Action full-test
```

No existing versioned build or evidence directory is removed automatically.
