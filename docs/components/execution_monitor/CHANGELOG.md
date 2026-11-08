# execution_monitor component history

## [0.4.0] - 2026-11-07

- **Changed:** Native Win32 `RecompDevMonitor.exe` now subscribes to CPU-neutral authenticated localhost controller diagnostics; no Python/Tk viewer is launched by the v0.4.9.21 preview. Terminal frame fields report host presentation count, native guest VDP counter and latest sampled frame independently. Source-attested previews can include an unqualified candidate frame-fingerprint manifest.
- **Validation:** Portable C++ JSON/protocol and bounded-history tests, source-attested native preview compile/run smoke and ZIP manifest tests pass locally; visual Windows two-window testing remains owner acceptance.
- **Compatibility:** Keeps original Python viewer source for audit only; no guest-memory access, code stepping, CPU-specific instructions, active DLL replacement or input-event causation claims.

## [0.3.0] - 2026-11-07

- **Changed:** Create ROM-free optional `recovery-seed.json` only from exact native final guest translation-gap state and matching live stop event. Display guest-blocked outcome separately from native process completion, showing distinct host and guest frame counters.
- **Validation:** Synthetic native compile/run, token-authenticated viewer and ROM-bound seed validation; real Windows GUI observation remains owner acceptance.
- **Compatibility:** Read-only viewer and original generated source remain unchanged. No guest modifications, CPU/console heuristic, or proof that input caused a stop.

## [0.2.0] - 2026-11-07

- **Changed:** Reconnect the existing CPU-neutral, independent read-only instruction viewer to current compiled-controller recovery artifacts. New `execution_monitor/job_preview.py` reconstructs a private generated project from a source-attested historical round, instruments only copied machine adapter code, compiles native preview and watches buffered instruction, frame, input-mask and stop events. The adapter now accepts the separate Mode 4 video plugin path as well as the previous inline renderer.
- **Validation:** Native Linux compile-and-run smoke verifies stop PC, original translated source unchanged, ROM-free checksummed ZIP, controller protocol and mock C++ job dispatch. Input-to-stop association is explicitly temporal, not proof that keypress caused a crash. Windows interactive game/monitor windows require owner acceptance.
- **Compatibility:** No changes to CPU, video, runtime, plugin ABI, original ROM, translated source, prior job or 642 protected files; no debugger breakpoints or guest mutation. Existing legacy modular launcher remains available.

## [0.1.0] - 2026-11-05

- **Changed:** Added independently versioned live execution monitor as a reusable, non-game-specific service.
- **Validation:** Generic broker and token tests, source staging checks, compiled native synthetic guest with controller event emission. Independent Windows GUI display must be verified by owner.
- **Compatibility:** Preserves the compiled controller v0.4.4, unchanged host DLL and CPU/video plugins, generated Z80 code and all 642 frozen historical files.
