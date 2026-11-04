# RecompDev handover — source-of-truth status

**Status:** Current as of 2026-11-04. This file must be updated with every accepted workspace release that changes engineering status.

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
