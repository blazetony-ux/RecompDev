# RecompDev component catalogue

**Status:** Current registry as of workspace v0.4.9.16. Every component has an independent version and its own [changelog](../development/RELEASE-PROCESS.md).

| Component | Scope | Implementation |
| --- | --- | --- |
| [analysis_integration](analysis_integration/README.md) | `production-workflow` | Controller-owned, approved Ghidra/Rizin analysis adapters and bounded native retry orchestration. |
| [controller](controller/README.md) | `production-entrypoint` | Compiled source-attested job manager, bounded native recovery scheduling, JSONL logging and retained temporary per-batch analysis provider. |
| [legacy.discovery](legacy.discovery/README.md) | `production-workflow` | Original discovery.engine analysis via the preserved Python adapter. |
| [legacy.preparation](legacy.preparation/README.md) | `production-workflow` | Original Ghidra/native preparation and authenticated function recovery. |
| [legacy.recovery](legacy.recovery/README.md) | `production-workflow` | Original reset/replay, verified-code discovery and native C++ compilation service. |
| [legacy.sms-campaign](legacy.sms-campaign/README.md) | `production-workflow` | Original multi-ROM Master System campaign runner. |
| [rd_audio_wav](rd_audio_wav/README.md) | `harness` | Headless PCM WAV file sink taking signed 16-bit samples. |
| [rd_cpu_z80](rd_cpu_z80/README.md) | `harness` | Small Z80 interpreter with explicit unsupported-opcode failure for synthetic harness fixtures. |
| [rd_discovery_jsonl](rd_discovery_jsonl/README.md) | `harness` | Harness event tracing to JSON Lines with bank/physical/cycles metadata. |
| [rd_display_ppm](rd_display_ppm/README.md) | `harness` | Headless P6 RGB PPM framebuffer writer. |
| [rd_game_fixture](rd_game_fixture/README.md) | `harness` | Hardcoded native instruction fixture with source-byte checking. |
| [rd_game_probe](rd_game_probe/README.md) | `harness` | Nontranslating probe-only game module for harness ROM exploration. |
| [rd_game_recomp_v0445](rd_game_recomp_v0445/README.md) | `harness` | Synthetic example native-code module generated using original P-code bridge. |
| [rd_input_fixed](rd_input_fixed/README.md) | `harness` | Deterministic configured button-state supplier for harness tests. |
| [rd_machine_sms](rd_machine_sms/README.md) | `harness` | Harness Master System bus, banking and VDP/PSG state backed by SMS runtime. |
| [rd_machine_synthetic](rd_machine_synthetic/README.md) | `harness` | Independent synthetic memory/bus/mapping machine to test interchangeability. |
| [workspace_governance](workspace_governance/README.md) | `workspace` | Git-managed documentation structure, changelog checks and release gates. |

**For live version numbers:** use `RecompDev.exe plugin status` or `workspace/components.json`; the component changelogs contain historical versions.

**Do not conflate scopes:** `harness` means the C++ modular harness, `production-workflow` means a preserved Python service adapter, `production-entrypoint` means the compiled orchestrator, and `workspace` means release/development tooling. A C++ DLL being active does not mean the native recovery adapter invokes it.

The currently registered components are declared by `workspace/components.json`. Only changed component versions may advance. Hardware modules not yet present in the registry (independent VDP, PSG, 68000 or PS1 modules) must not be described as delivered.

## Added in v0.4.8

- [production_translation](production_translation/README.md), `production-workflow`: hash-locked selection of the complete historical generator, with per-round provenance; not a new native DLL.
- [workbench](workbench/README.md), `developer-tool`: read-only SQLite catalogue service independent of the compiled controller.

## Added in v0.4.8

- [rd_runtime_host](rd_runtime_host/README.md), `production-presentation`: native, machine-independent window/PCM/input host; generated source adapter stages outside Git.

## Added in v0.4.9

- [input_recovery](input_recovery/README.md), `production-workflow`: source-only, independently versioned guest-cycle input recorder, replay verifier and bounded source-attested recovery orchestrator. The already deployed runtime-host DLL and all existing CPU/translator components stay unchanged.

- `rd_video_sms_mode4` — independently compiled Master System Mode 4 sprite/video plugin, production-video scope.
- `sms_video_integration` — source-only generated native video bridge, production-video-integration scope.

`movement_trace` (`production-diagnostics`) independently versions the opt-in guest input/port read/scroll/SAT observation path. It does not alter input mapping or any compiled runtime/CPU/video DLL.

## Added in v0.4.9.4

- [state_observer](state_observer/README.md), `production-diagnostics`: platform-neutral read-only guest memory-region observer with provider metadata, bounded change logs and candidate correlation.
- [movement_trace](movement_trace/README.md), `production-diagnostics`: SMS adapter for generic memory observation plus port/scroll/SAT tracing.

## Added in v0.4.9.5

- [controller_diagnostics](controller_diagnostics/README.md), `controller-diagnostics`: single typed local event subscription service.
- [execution_monitor](execution_monitor/README.md), `developer-debugger`: independent subscriber GUI and native telemetry producer.
- [runtime_host_integration](runtime_host_integration/README.md), `production-host-integration`: source-only wiring and evidence, not a new compiled host DLL.

## Added in v0.4.9.6

- [discovery_integration](discovery_integration/README.md), `production-workflow`: controller-managed, independently versioned read-only discovery audit, historical source-scoped task inventory, raw-sector disc file inspection and validated candidate mapping. Does not change existing native game runtime or add CPU translators.

## v0.4.9.7 candidate native discovery plugins

- [rd_format_sms](rd_format_sms/README.md) — SMS header and Z80 family.
- [rd_format_md](rd_format_md/README.md) — Sega 68000 cartridge structure and reset vector.
- [rd_format_ps1](rd_format_ps1/README.md) — PS-X EXE/ISO9660 2048/2352 raw sectors.

These are compiled DLL providers loaded by the native controller, not Python discovery wrappers. v0.4.9.7 remains unaccepted until real-source translation/build and owner Windows tests pass.

## Release infrastructure (v0.4.9.8 candidate)

- [release_installer](release_installer/README.md), scope `workspace`: one permanent Git-managed root installer for verified source ZIPs, compilation, tests, Git control, and safe conditional activation. This is not a production runtime plugin or per-release launcher.

## Added in v0.4.9.10

- [rd_translation_pcode](rd_translation_pcode/README.md), scope `production-translation`: independent compiled P-code translation DLL, authenticated ROM/Ghidra IR to freshly generated full preserved nativepilot application or controller-executable game DLL. Actual real Shinobi 1,800-frame equivalence has **not** yet been qualified, and historical automatic recovery remains transitional.

## Native SMS cutover candidate (2026-11-07)

The independent maintained `rd_sms_native_runtime` machine-state DLL is registered in `workspace/components.json`; see [its component page](rd_sms_native_runtime/README.md) and [release acceptance gates](../releases/v0.4.9.10.md). New native game projects link it plus separate `rd_video_sms_mode4` and `rd_runtime_host` DLLs. The 642 frozen source files remain reference-only.

## v0.4.9.13 direct analysis provider

- [analysis_integration](analysis_integration/README.md) `0.2.0`: active RecompDev-owned Rizin CLI/provenance/ANSI-aware JSON adapter; Ghidra/reconciliation still temporarily depend on historic Python. No new compiled DLL is claimed.
