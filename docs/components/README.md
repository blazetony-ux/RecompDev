# RecompDev component catalogue

**Status:** Current registry as of workspace v0.4.9. Every component has an independent version and its own [changelog](../development/RELEASE-PROCESS.md).

| Component | Scope | Implementation |
| --- | --- | --- |
| [controller](controller/README.md) | `production-entrypoint` | Compiled command entry point; runs workspace manager commands and preserved Python orchestration. |
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
