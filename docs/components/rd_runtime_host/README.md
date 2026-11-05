# rd_runtime_host — generic native presentation host

**Scope:** `production-presentation`, canonical independent component version in [`workspace/components.json`](../../../workspace/components.json). Host library built from `runtime_host/src/host.cpp`, public C ABI in `runtime_host/include/rd_runtime_host.h`. Target `rd_runtime_host` can be compiled and activated without rebuilding the controller, Z80 or machine plugins.

## Responsibilities and boundaries

- **Input:** 64-bit abstract button mask (Up, Down, Left, Right, A/B/C, Start, Select) via API; Win32 keyboard backend uses arrows, Z/X, Enter and Escape. Button meaning for a console is assigned by its machine/input plugin, not by the host. The Windows launcher also captures sampled button-mask transitions in an upload-ready `input-events.jsonl`, so Start-button delivery can be diagnosed without logging raw keystrokes.
- **Video:** BGRA8888 `width` x `height` framebuffer, dynamically sized up to 4096 x 4096; Windows window renderer reuses the frozen, verified OS presentation layer. Portable headless handling uses the same ABI and deterministic frame fingerprint.
- **Audio:** signed PCM16 interleaved across 1–8 channels at a declared sample rate, with an optional Win32 speaker. The initial Windows speaker uses the preserved mono backend, downmixing multichannel PCM for playback; the headless fingerprint is computed from the original multichannel samples. Independent headless counters capture sample count and fingerprint. This does not generate PSG or SPU waveforms.
- **Lifecycle:** version-checked C ABI v1, create/submit/pump/stats/destroy; no C++ STL types or machine-specific structures cross the DLL boundary.
- **Native game bridge:** `runtime_host/bridge.py` replaces only presentation shims in an **external cached copy** of the already-generated native project. `runtime_host/launch.py` verifies the ROM SHA against the authenticated generation report, builds only `RecompDevNativeApp`, launches it and produces a ZIP under `RecompDev-Evidence/v0.4.8/runtime-host/`.

The existing legacy native application supplies the **same guest-generated frames** and input callbacks in both headless and interactive modes. This is not a separate Z80 interpreter or an independent game engine; it does not touch the frozen legacy translator or generated `translated.cpp` instruction semantics.

## Limitations and validation

**Not delivered:** ROM-free standalone execution, independently verified Shinobi gameplay, window mode on non-Windows machines, audio synthesis fixes, standalone controller/game module ABI beyond the host-presentation boundary. Currently the generated application **still opens the original ROM**, even though its instruction translations are native. No assertion of PlayStation/Mega Drive gameplay: only the host API is system-neutral, those source execution modules are not yet integrated.

Windows acceptance: build only `rd_runtime_host` and `rd_runtime_host_smoke`, pass the portable smoke plus existing tests, install the versioned DLL, and use `tools/Run-Native-Game.ps1` with the previous 600-frame native project. First real-game launch requires Windows validation and might uncover additional native input/hardware issues. Close with Escape; wait for `RECOMPDEV_EVIDENCE_ZIP` to upload diagnostics.

See [the component changelog](CHANGELOG.md), [release notes](../../releases/v0.4.8.md) and [project handover](../../project/HANDOVER.md).
