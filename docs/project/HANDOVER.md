# RecompDev handover — source-of-truth status

**Status:** Current as of 2026-11-05. This file must be updated with every accepted workspace release that changes engineering status.

## Where everything lives

`C:\Projects\RecompDev` is the Git-managed source checkout, initially imported with Git commit `0ba3795b1ad6ba0696c1a0bb71552a593d8ce233` and tag `workspace/v0.4.4`. Build: `RecompDev-Build`; runtime: `RecompDev-Runtime`; cache: `RecompDev-Cache`; owner catalogue: `RecompDev-Data`; logs/evidence: `RecompDev-Evidence`; archives and Git bundles: `RecompDev-Archive` (all siblings under `C:\Projects`). Do not write generated binaries or logs into the checkout.

v0.4.5 is a **documentation/tooling workspace snapshot**, not a new compiled controller. Controller `0.4.4` and existing compiled DLL versions `0.1.0` are unchanged. `workspace_governance` starts at `0.1.0` and owns release/documentation validations. See [components](../components/README.md).

## Existing, real pipeline

The compiled `RecompDev.exe` invokes preserved `legacy.discovery`, `legacy.preparation` and `legacy.recovery` Python adapters from frozen v0.4.0.45. The separate `RecompDevHarness.exe` loads ten interchangeable C++ DLLs built from `harness/plugins/`, but those DLLs do **not** yet drive production recovery. New architecture must not falsely report that they do.

## Windows-verified facts from owner logs

- v0.4.4 installer: external CMake build, full test suite passed, 11 compiled components deployed (controller plus ten plugin DLLs); source preservation 642/642; Git release bundle created externally.
- Isolated `rd_cpu_z80` build produced the same hash as its active `0.1.0` DLL. `git status --short` was empty after the build.
- Active plugin registry showed ten C++ plugins scoped `harness`, four legacy services scoped `production-workflow`.
- Shinobi v0.4.2 native recovery: three recovery rounds, `709841` maximum native steps, `120` frames, `3372` newly recovered addresses across rounds, `32942` VDP writes, `128` CRAM writes, `34` accepted maskable interrupts, `11` PSG writes, and a silent final WAV. Reports explicitly state hardware/gameplay parity NOT established.
- v0.4.3 reviewer found 120 counter rows, seven WAV diagnostics (all silent), eight session records and no raw VRAM/CRAM; useful review output but insufficient for source-tile recovery or independent parity.

## Critical restrictions

Preserve the original 581-file v0.4.0.45 and 61-file harness v0.3 baselines unchanged under `legacy/` and `baselines/`. Avoid overwriting the owner catalogue; take per-run working snapshots. No new native release is gameplay-qualified just because it compiles, executes or reaches 120 frames.

## Next action for a developer

Implement a **versioned production plugin bridge**, initially for Z80 or the translator, and prove with a real ROM that a swapped plugin is invoked on actual source-attested instructions and recorded in the central evidence. Do not demand another full workspace reinstall. Read [architecture](../architecture/ARCHITECTURE-CONTRACT.md), [current pipeline](../recompilation/PRODUCTION-PIPELINE.md) and [release process](../development/RELEASE-PROCESS.md) before editing.

## Handover maintenance rule

Record factual progress (including source paths, test names and failure outcomes) after each accepted engineering release, update the roadmap and relevant component changelogs, and keep this handover current for subsequent conversations. The updater must not invent test results or claim future validation.

## 2026-11-04 — v0.4.6 phase-1 production gate

A coordinated incremental release adds `production_cpu_bridge` 0.1.0 and extends `rd_cpu_z80` 0.2.0. The compiled controller remains 0.4.4, unaffected DLLs stay 0.1.0, and legacy adapters remain 0.4.0.45. Actual Z80 source-attested instructions are now passed through the selected active CPU DLL and its SHA-256 is verified before **legacy** native translation/recovery begins. A plugin rejection stops that run, while missing/older gate support is explicitly reported (strict `--cpu-plugin required` refuses it). The native translator and runtime are **not yet routed through the DLL**. New evidence includes production gate decisions and plugin hashes. Tests include a synthetic source-authenticated export, actual preserved native compilation and an alternate rejecting native library on Linux; the owner's Windows Shinobi run is outstanding. See [production pipeline](../recompilation/PRODUCTION-PIPELINE.md) and [release notes](../releases/v0.4.6.md).

## 2026-11-04 — v0.4.7 preservation and Workbench

The next workspace release adds `production_translation` 0.1.0 as a hash-locked adapter to the **entire existing** native P-code generator, invoked by the original reset/replay recovery driver through a child-process boundary. This corrects the previous direction toward re-implementing a small Z80 translator. The new `production-translation.json` witness records provider version and SHA, original generator hash and actual generation calls. The original runner is still available with `RECOMPDEV_TRANSLATOR_MODE=legacy-direct`. The CPU v0.2.0 DLL remains a source-admission gate and was not rebuilt.

A separate Python `workbench` 0.1.0 service browses the owner SQLite catalogue read-only on 127.0.0.1, with logs under `RecompDev-Evidence/v0.4.7`; launch via `tools/Start-Workbench.ps1`. Its purpose is browsing, not job control. The user's earlier **600-frame Shinobi observation must not be reported as a new pass**: the latest independently examined v0.4.2 evidence reaches 120 frames; reproducing an aligned 600-frame result remains an explicit next acceptance gate.

See [v0.4.7 release](../releases/v0.4.7.md) and [Workbench](../components/workbench/README.md).

## Workspace v0.4.8: generic host integration (2026-11-05)

The separately buildable `rd_runtime_host` 0.1.0 exposes a CPU/machine-neutral native C ABI for frames, audio, buttons and lifecycle. A generated-project adapter wraps the preserved `RecompDevNativeApp` window/audio interfaces while keeping `translated.cpp` and the frozen v0.4.0.45 source unchanged. Windows window rendering and live Shinobi input remain unverified until owner testing; the portable headless ABI and synthetic compiled game path have automated tests. **The native game still loads the original ROM** and does not yet meet the ROM-independent deliverable. Do not divert engineering into Workbench expansion; priority remains validated interactive native gameplay, ROM-free packaging and hardware correctness.

See [runtime_host](../components/rd_runtime_host/README.md) and [v0.4.8 release](../releases/v0.4.8.md). Other component versions must stay unchanged.

## Workspace v0.4.9 — input-driven native recovery (2026-11-05)

**New owner-verified facts since v0.4.8:** The current preserved native recovery reached **600 Shinobi frames** in v0.4.7, 4,017,333 reported steps, and produced a recognisable title screen. The new generic Windows runtime reproduced its final framebuffer byte-for-byte. The user pressed Enter (Master System Pause/NMI) during another run, reaching frame 894 and missing code at `0x56C7`; pressing **Z** (controller Button 1) advanced to a distinct mission/introduction screen but then stopped at frame **201** and untranslated ROM address **`0x7BE8`** after 1,259,709 reported native steps. These are *execution observations*, not independently validated game correctness, actual controllable play, sound output or ROM independence.

**Next source-only component:** `input_recovery` 0.1.0 (see [component specification](../components/input_recovery/README.md)). It instruments the disposable native frontend to record logical input masks in **guest CPU cycles**, checks whether those events reproduce the original stop on the same generated guest code, and only then invokes the preserved verified-coverage recovery with the same replay. The last owner's v0.4.8 ZIP has only `elapsed_ms` transitions, so the first replay **may diverge**; if it does, the system must stop and request a fresh exact-cycle capture rather than claim `0x7BE8` has been recovered. Windows deployment of v0.4.9 remains unverified until the owner applies the patch.

Run via `tools/Recover-Native-Input.ps1` using the original ROM and optionally the prior ZIP. The entire source tree and 642 original files remain protected; the controller, Z80 DLL, presentation DLL, Workbench and other unchanged components must not be rebuilt. Evidence belongs under `RecompDev-Evidence/v0.4.9/input-recovery` and `.../runtime-host`. **No live hotpatching, no ROM-free game and no guaranteed incremental *per-function* compilation** are claimed. Preserve source hash, guest stop, input replay SHA and accurate failure statuses in every handover.

**v0.4.9.1 patch:** External short-path game CMake builds, original history import reenabled when explicitly selected, and postflight suppressed on build failures; real Shinobi progression still unverified.

## v0.4.9.2 production video work (2026-11-05)

Sprite omission was confirmed in the preserved Mode 4 renderer during an interactive Shinobi test. `rd_video_sms_mode4` is a replaceable compiled video-only plugin and `sms_video_integration` is the source-only bridge that modifies only generated project staging. It uses the original 16 KiB VRAM, 32-byte CRAM and 16 VDP register bytes; no game-specific assembly, CPU or controller code is embedded in the video plugin. The native launcher verifies the active DLL SHA and exports per-frame SAT/sprite statistics to `sms-sprite-stats.csv`; the next Shinobi evidence ZIP is the first real-ROM acceptance gate. The previous stop `0x1E62` remains an *untranslated-code* issue, independent of drawing. Do not update the original legacy renderer or collapse the video DLL into the generic host. The new sprite implementation is not frame-exact VDP parity (status flags/scanline side effects, SMS1 zoom variants remain open).

## Workspace v0.4.9.3 — movement correctness investigation (2026-11-05)

Real live Shinobi gameplay displays player/enemy sprites, but the owner reported movement apparently reversing partway through a session. The last host input event log shows normal held directions and execution stopped separately at untranslated `0x1E09`. Do not change keyboard mapping based on that alone. `movement_trace` v0.1.0 stages strict observation-only instrumentation into copied generated `live_sms.hpp` and `runtime.cpp`, recording guest-cycle input, actual I/O port 0xDC/0xDD reads, video scroll R8/R9, and raw SAT coordinates. Invoke `tools/Run-Native-Game.ps1 ... -MovementTrace`; inspect `movement-diagnostics.json` plus raw traces in its ZIP. No player sprite ID or world coordinate can be inferred automatically. This workspace release requires Windows testing; all active compiled DLLs retain v0.4.9.2 versions. Immutable v0.4.0.45 recovery code and 642 historical sources MUST remain untouched.

## v0.4.9.4 diagnostic provider contract (2026-11-05)

The owner requires all components **decoupled and interchangeable**. Guest-state telemetry uses a generic independently versioned `state_observer` memory-region interface; it must never contain Master System `State::ram`, Z80 instructions or Shinobi RAM address assumptions. `movement_trace` 0.2.0 owns the first SMS-only 8 KiB provider; Mega Drive and PS1 would each supply their own provider without rewriting the common recorder. Correlation only compares inputs and memory changes when the provider's cycle domain matches. Current 2400-frame Shinobi evidence shows correct guest controller reads but intermittent unresponsive movement; memory diagnostics do not fix it, and actual Windows evidence and independent emulator comparison remain necessary. Historical translator and active DLLs are unchanged. See `docs/releases/v0.4.9.4.md` and `docs/components/state_observer/README.md`.
