## [0.4.4] - 2026-11-08

- **Changed:** Preserve bounded exact guest-cycle input transitions as source-hashed `guest-input-cycles.csv` in the immutable preview diagnostics ZIP and offer a receipt with source ID, job ID, result, ZIP path/hash and replay availability to the compiled controller. Capture loss or invalid event order suppresses automatic recovery eligibility.
- **Validation:** Python replay and archive tests verify event deduplication, replay schema, SHA and negative malformed input; independent Windows interactive two-window test remains blocked.
- **Compatibility:** Default live preview and read-only monitor retain prior semantics; no guest-state mutation, monitor-to-CPU direct link or claim that a key press causally induced the stop.
- **Windows CTest candidate correction (2026-11-08):** `v04919_controller_preview_native` failed two legacy preview fixtures because new receipt code directly read a missing `Options.result_json` attribute. The receipt is now optional for pre-existing callers (`getattr` default empty); requested receipts still use the existing path and immutability checks. The original owner Windows run passed 81/82 CTests, and the corrected candidate requires a new Windows full-suite validation before promotion.

# execution_monitor component history

## [0.4.3] - 2026-11-08

- **Changed:** RUNTIME-004 stdout preview collector now distinguishes over-512-KiB diagnostic output from a trustworthy unique terminal record. Stream one bounded schema-checked `NATIVE_APP_RESULT` up to a hard 16-MiB cap, and explicitly disclose diagnostic-log oversize without changing raw output.
- **Validation:** Python regression exercises a >512-KiB 2,400-frame terminal result, hard cap, missing/duplicate/invalid records, nonzero native process exit and immutability of stdout. Linux focused suite passed; full Windows MSVC acceptance and actual Shinobi 2,400-frame retest pending.
- **Compatibility:** Raw JSONL and stdout logs remain immutable, native output ABI and game DLLs unchanged. Capture-complete summary is not independent gameplay, graphics, audio, input or state parity proof.


## [0.4.2] - 2026-11-08

- **Changed:** Reusable integration without CPU/game assumptions.
- **Validation:** Synthetic tests locally; owner Windows regression gates pending.
- **Compatibility:** Schema, ROM and immutable evidence contracts preserved; runtime parity not asserted.

- **Sustainable watches:** Exact watched-PC hits are counted, while detail output is bounded: first 32 per PC, ordinary stride samples, summaries every 4096 hits, and final per-PC/global counters. Coalesced hit count is explicit, not silently portrayed as every-hit instruction evidence. Maps limited to 256 unique PCs; excess counted as unbucketed.
- **Independent live display:** Bounded 1/16 live instruction forwarding to authenticated controller viewer, preserving the native sampled JSONL and all input/stop/frame/summary/notice events. Flushes 256 instruction samples or at critical boundaries; seals the trace and final summary in the *instrumented copy* of the generated frontend. This reduces, but does not promise zero, transport loss.
- **Audit:** Summary includes watched-PC totals, intentionally coalesced hits, intentional display sampling and capture-truncation notices. 120k hot-PC stress regression passes locally; Windows 76/76 CTests and real UI observation pending. No CPU-specific code, breakpoint/control commands or reference parity claim.


## [0.4.1] - 2026-11-08

- **Changed:** Standalone Win32 monitor performs off-thread bounded event ingestion and 100 ms timer-driven UI updates rather than rebuild/scroll on each high-volume event. Native search by text/PC/physical address/class/event, next/previous, matched-only and follow controls. The producer captures explicitly watched CPU PC/range hits regardless of ordinary sample stride; guest execution stays uninfluenced. Terminal PC is distinct from previous sample SP/step and display transport loss is disclosed.
- **Windows stress correction:** Explicit `Publisher::finish()` flush/close before the stress fixture removes its temporary JSONL trace; Windows cannot delete a still-open file as Linux can. The first owner v0.4.9.22 candidate failed 1/74 tests with process exit `0xC0000409`; corrected candidate is pending owner MSVC rerun.
- **Validation:** Linux native source build plus 50,000-event queue burst, 40,000 instruction-model events, exact watched-address sampling override, source-attested preview regression, and control-event tests. Windows GUI responsiveness still requires owner testing.
- **Compatibility:** Read-only protocol remains v1 and hardware neutral; no memory read, CPU stepping, breakpoints, ROM parsing, Tk dependency, console DLL change or independent gameplay-parity claim. Full native event evidence remains separate from bounded GUI/display excerpts.

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
