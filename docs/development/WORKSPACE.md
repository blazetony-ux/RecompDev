# Local workspace: build, test and rollback

**Status:** Current for the permanent v0.4.4+ Git checkout. Last verified against repository source: 2026-11-04.

The checkout at `C:\Projects\RecompDev` contains source and docs. `RecompDev-Build/cmake` contains the existing CMake configuration; `RecompDev-Runtime` contains activated binaries and versioned DLL backups. `RecompDev-Evidence` holds captures and logs by controller version. The project defaults can be overridden with `RECOMPDEV_PROJECTS_ROOT` for workspace tools.

## Inspect without changing anything

```powershell
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin status
git -C 'C:\Projects\RecompDev' status --short
git -C 'C:\Projects\RecompDev' tag --list
```

The supported command is `plugin status`, **not** `plugin list` in controller v0.4.4.

## Ordinary compiled plugin development

```powershell
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin build rd_cpu_z80
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin test rd_cpu_z80
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin bump rd_cpu_z80 patch
# Edit harness/plugins/cpu_z80.cpp and append a meaningful entry to
# docs/components/rd_cpu_z80/CHANGELOG.md before accepting.
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin accept rd_cpu_z80
```

A plugin accept checks the source boundary, version increase, documentation entry, isolated build, targeted tests and 642-file source preservation before commit and activation. Unchanged components retain their versions. Compiled DLL replacement currently affects **the harness only**; see [real pipeline](../recompilation/PRODUCTION-PIPELINE.md).

Documentation-only changes are committed without changing an unrelated component:

```powershell
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin docs-check
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin docs-accept
```

Rollback switches to the previous stored DLL and does not reset Git source history:

```powershell
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin rollback rd_cpu_z80
```

## External outputs and safety

The owner production catalogue in `RecompDev-Data` is not used as a writable test database. Generated native code/cache is not source. New files inside `legacy/` or `baselines/` violate preservation policy. Keep original versioned installations until independent migration checks establish complete coverage.
