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

## Phase 1 production CPU admission bridge (workspace v0.4.6)

For Z80 native recovery, `modular/controller.py` now calls `modular/cpu_production.py` after the frozen `pcode_verify` function authenticates the actual Ghidra export, and **before** dispatching to `legacy.recovery`. The module resolves `rd_cpu_z80` from the active runtime lock, checks both the selected DLL and immutable version-store SHA-256, then passes each verified physical ROM instruction to the native `rd_z80_source_gate_v1` C ABI. A rejected instruction or compromised DLL stops that run; other platforms are not silently passed to a Z80 plugin.

The selected version/hash, admitted instruction count, opcode-family counts, length-check coverage and fallback status are included in `production-cpu-gate.json`, `controller-report.json` and `run-provenance.json`. This is a real swappable production **source-admission** mechanism but not a native CPU execution or translation plugin cutover: all translation and gameplay execution remain performed by the original source-authenticated native P-code pipeline. Do not describe it as full native CPU integration.

Use `--cpu-plugin required` to demand a currently installed gate-enabled DLL, `auto` for a clearly labelled fallback when no compatible gate has ever been installed, or `legacy` for explicit bypass. Selected corrupt/rejecting binaries fail closed. Tests: `python -B -m unittest modular.tests.test_production_cpu -q` (native Z80 DLL must be built first); original preservation and full CTest gates still apply.

## v0.4.7 source-preserving production translator adapter

The original generator is **not reimplemented** in a new Z80 DLL. `production_translation/run_recovery.py` runs the exact original v0.4.0.45 recovery driver with its `generate_project` callable supplied by a hash-verified versioned provider. The default provider delegates to the unchanged `nativepilot.generator.generate_project`, including all P-code operations, overlays, hardware and native compilation it already supported. The adapter runs in a separate Python process; no compiled controller or native DLL is replaced. Detailed per-round provenance is written to `production-translation.json`, with a summary in the external evidence ZIP. Use environment variable `RECOMPDEV_TRANSLATOR_MODE=legacy-direct` to run the original driver directly. A corrupt or unregistered provider fails closed instead of pretending that a new translator works.

This proves a selectable **production code-generation callable** while keeping full legacy behaviour; it is **not** proof of a fully portable IR or a native CPU translator ABI. A same-source, same-input 600-frame Shinobi comparison remains outstanding. See [provider documentation](../components/production_translation/README.md).

## Generic native presentation host (workspace v0.4.8)

The new [`rd_runtime_host` interface](../components/rd_runtime_host/README.md) defines a CPU- and machine-neutral BGRA frame, PCM16, input and lifecycle boundary. The adapter stages a *copy* of the preserved native game's generated project outside Git and replaces only presentation headers. No source-verified instruction dispatch is rewritten. The same native game execution and machine devices feed either interactive/window or noninteractive/capture modes; guest correctness is still independently unqualified.

Unlike a ROM-free standalone game, the current generated native application still verifies/reads the owner ROM at runtime. The runtime launcher records guest stop reasons and produces evidence ZIPs under the central evidence root. This is a **presentation integration**, not a new instruction translator, a machine plugin, or a claim of playable Shinobi.

## Input-driven recovery (workspace v0.4.9)

The existing generic native presentation host can now export a `RECOMP_INPUT_CYCLES_V1` log sampled at guest CPU cycles via staged `interactive.cpp` instrumentation, without modifying frozen source, native `translated.cpp` or machine plugins. The new [input recovery component](../components/input_recovery/README.md) validates the previous run's ROM hash and event schema, runs a bounded native replay to reproduce the same guest stop (status, PC and frame count), then invokes the existing compiled controller's source-verified reset/replay with `--input-events`, `--history-root` and recovery budgets. It does **not** introduce a second translator or an emulator fallback.

The v0.4.8 Shinobi evidence contains wall-time transitions only; converted replay timing is `HOST_MILLISECONDS_ESTIMATED` and may fail the stop-match gate. This is the proper diagnosis, not justification for compiling incorrect guessed instructions. The complete historical v0.4.0.45 engine and existing production runtime remain unchanged; incremental recompilation currently applies to generated app build targets, not individual guest instructions or functions.
