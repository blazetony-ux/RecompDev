# Real-ROM native recompilation and recovery

## 2026-11-07 — v0.4.9.10 active SMS runtime / video / host DLL cutover

- New `rd_sms_native_runtime` **0.1.0** compiles the maintained SMS runtime port independently. `rd_machine_sms` **0.4.0** now links this DLL instead of directly compiling frozen historical `runtime.cpp`; the CPU Z80 plugin uses maintained cycle headers.
- `rd_translation_pcode` **0.3.0** emits fresh native games using active `runtime_sms/templates` and builds independent SMS runtime, Mode-4 video and generic presentation DLLs. `RecompDev.exe` **0.4.9** passes the authoritative source root to native CMake; `rd_runtime_host` **0.1.1** uses maintained hardware contracts. `rd_video_sms_mode4` C ABI is unchanged.
- The preceding **real-ROM Shinobi run of 120 frames / 709,841 native steps / visible red title** was generated *before this runtime cutover*. It is the reference baseline and must not be presented as test evidence for the newly rewired renderer or interactive input. The correct Ghidra base export is on the Windows owner computer, not in this offline build environment; a similarly named export for another ROM is rejected by the SHA gate.
- Offline C++ build and full independent native-pilot differential fixture pass. `v04910_production_native_sms_runtime_cutover` verifies bank-6 mapping, video and headless frame-host ABI; `v04910_production_legacy_boundary` guards against reintroducing frozen production source dependencies. Tests against the real ROM currently verify **620 discovered instruction candidates** only, not new-game display or gameplay. Exact Windows runtime loading, frame hashes, input semantics and the required 1,800-frame / second-ROM gates remain **BLOCKED**.
- The old `legacy.discovery`, `.preparation` and `.recovery` Python services have not yet been entirely unplugged. The SMS C++ State export is same-toolchain, not fully replaceable machine-neutral C ABI. Preserve the 642 frozen original files unchanged. Candidate only; no tag, commit or active install until the acceptance gates are genuinely achieved. The Git-managed permanent installer is unchanged.

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

## Native controller game-DLL execution port (v0.4.9.9)

`RecompDev.exe --stage native-execute --rom <original-rom.sms> --game rd_<source-specific-module> --steps 200 --out <unique-external-prefix>` uses the original C++ harness game-execution loop directly inside the compiled controller. The game DLL must export `rd_game_source_sha256_v1` and `rd_game_source_size_v1`; exact ROM identity and per-instruction bytes are verified before executing compiled native instructions. Default fail-closed native-only mode refuses untranslated offsets. Use `--allow-fallback` only to explicitly opt into the old limited synthetic Z80 interpreter; it is not the preserved complete production translator.

The unchanged hash-locked original `nativepilot.generator` / Ghidra P-code compiler still generates source-specific project output through the transitional Python provider. **It has not been ported into a translation DLL**, so the completed universal real-ROM pipeline remains outstanding. DLL discovery is a source-structure evidence operation, not a substitute for P-code semantics.

## v0.4.9.10 direct native P-code translation and full original game runtime

The compiled `RecompDev.exe --stage native-translate` loads ABI-checked [rd_translation_pcode](../components/rd_translation_pcode/README.md) and directly translates authenticated Ghidra P-code export JSON into a newly compiled native project. The default backend emits both full preserved historical nativepilot runtime executables; `--backend game-dll` emits a DLL runnable by `--stage native-execute`. It reads, but never modifies, frozen C++ runtime templates. Full-ROM identity, instruction source bytes and per-block Ghidra provenance are checked before emission; optional source-matched previous `bank-functions.json` recovery exports are imported via `--history-root`. Fixture output was compared to the original Python generator and matched native state/banking/timing outputs. This is meaningful **compiled** migration of P-code lowering, not a new trivial instruction-length decoder. It is not proof of full semantics or actual Shinobi execution: *initial Ghidra analysis* and *runtime-triggered recovery* are still performed through the previous Python workflow; the full-native-runtime machine remains SMS-specific; and no real commercial ROM execution has yet qualified the generated code. Read the [v0.4.9.10 release record](../releases/v0.4.9.10.md), whose gate explicitly remains BLOCKED.

## Native source-decoder and bounded runtime-stop recovery candidate (v0.4.9.10 follow-up)

The C++ Z80 CPU plugin source-lifts verified ED block I/O and CB BIT/RES/SET, conditional RET and selected base instructions, with conservative SMS mapper effects. The compiled controller can accept repeated `--runtime-gap-report` paths (PILOT_RESULT log or standalone JSON) while running `--stage native-translate`; it independently validates the observed native status, ROM size, bank mapping and physical address through the machine DLL, then invokes `--stage discover` to source-verify the code. The translator consumes only these authenticated discovery blocks and verified Ghidra exports, never executable strings from reports. Large native translations are sharded by stable physical-offset hash to limit rebuilding to changed C++ objects. The user-installed v0.4.9.9 has no such interface, and this v0.4.9.10 work remains uninstalled pending Windows validation and real-game parity. The newly built Linux Shinobi pilot reached 338,531 guest instructions and 64 elapsed frames, not the prior 1,800-frame run. Automatic analysis/export generation, iterative native-recovery orchestration, and full animation/input parity remain unfinished.


## v0.4.9.11 controller-owned native analysis/recovery path

Use `RecompDev.exe --stage native-orchestrate` with `--rom`, fresh `--out`, matching `--plugin-dir`, and either authenticated `--export` or an explicitly allowed `--ghidra` executable (optionally `--rizin`). The temporary `analysis_integration` subprocess adapter consumes the historical Ghidra/Rizin *analysis* providers read-only. Source identity and per-instruction byte SHA-256 are checked independently; Rizin entries nominate initial-mapper discovery only. The native DLL translator emits source-attested C++, then the new app reports an actual untranslated-code stop; a finite bounded loop recompiles only if new code coverage is obtained. No `legacy/` or `baselines/` production runtime is compiled or executed, and all output remains outside the source checkout. This is SMS/Z80-limited and must fail closed on all other hardware until a native provider dispatch contract is complete. Acceptance remains BLOCKED for owner real tools, parity, 1,800-frame and another real ROM.
