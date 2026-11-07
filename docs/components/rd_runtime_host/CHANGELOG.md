# rd_runtime_host — independent component history

## [0.1.1] - 2026-11-07

- **Changed:** Fresh native translation projects directly build and link the existing generic RD_Host C ABI for fullscreen/headless frame presentation, PCM output and live button polling, instead of copying historical `interactive.cpp` Windows presentation into the application. The compiled host now consumes maintained hardware headers from `runtime_sms/include`, not the frozen legacy tree.
- **Validation:** Existing independent headless host smoke and generated-game compatibility tests pass on Linux, alongside the new SMS state/video/host integration smoke. The native Windows window/speaker/input path and live Shinobi controls remain to be verified on the owner's computer.
- **Compatibility:** The exported RD_Host ABI version remains `0x00010000`; this is an integration/source-boundary change, not a new host protocol. Original preserved sources, DLL interface ownership and Windows release installer are unchanged.

## [0.1.0] - 2026-11-05

- **Changed:** Introduced a new native DLL with a CPU-, game- and machine-independent C ABI to present BGRA frames, forward abstract button masks, accept interleaved PCM16 audio (1–8 channels, with Windows mono downmix), and support a headless backend. Implemented a generated-project shim that delegates existing source-attested native application video/audio/input to this versioned host instead of tying presentation to the game executable.
- **Validation:** Linux builds and ABI smoke tests across 256×192, 320×240 and 640×480 framebuffers, PCM format checks, synthetic authenticated native-project recompilation and execution, wrong-ROM rejection, source-staging integrity, plus historical preservation and regression suite gates. Windows rendering remains to be validated on the owner's PC.
- **Compatibility:** No changes to the compiled controller, existing Z80 and machine DLLs, immutable legacy translator, or source-authenticated generated instruction code. Requires original ROM locally to launch the generated app; it does not establish ROM-independent games or pixel/audio correctness.
