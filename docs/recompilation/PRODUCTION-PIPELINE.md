# Real-ROM native recompilation and recovery

**Status:** Integrated through preserved service adapters; not yet a fully pluggable native production engine.

## Stages

- `discover`: `modular/cli.py` uses `legacy.discovery` → frozen `discovery.engine`, with per-run working SQLite catalogue snapshot and source-hash provenance.
- `prepare`: `legacy.preparation` → frozen `nativeprep.engine`; Ghidra determines candidates and exports source-attested instructions. Missing Ghidra/tool failure remains a blocker, not successful translation.
- `recover`: `legacy.recovery` → `tools/Run-Continuous-Recovery-v0445.py`, which invokes frozen `nativecore/continuous_recovery_v0436.py`. It constructs native C++ projects and compiles/executes them with bounded recovery and reset/replay.

The modular recovery manager in `modular/recovery_manager.py` can request multiple rounds and reuse verified-code coverage caches. Exit `FRAME_BUDGET_REACHED` means the requested frame count was observed; it is not evidence that the game is playable or independent of the ROM.

## Verified facts and limits

The user-provided Shinobi recovery ran three bounded rounds and ultimately reported 120 frames and 709,841 native steps with 3,372 recovered instruction addresses. Source authentication and compilation succeeded, but the hardware audio was silent and no independent reference parity was established. See [research observations](../research/SHINOBI-RECOVERY.md).

## Required plugin cutover gate

The production services above currently bypass the ten C++ harness DLLs. The next migration must invoke a selected versioned CPU/translator or machine plugin on **real** source-attested instructions. Evidence must record component ID/version/hash and demonstrate an isolated swap and rollback without modifying legacy source. This gate is not passed by compiling or swapping `rd_cpu_z80.dll` in the harness alone.
