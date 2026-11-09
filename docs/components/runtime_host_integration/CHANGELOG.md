## [0.2.0 paused-input edge preservation] — 2026-11-08 (source-only)

- Extend maintained runtime-host interface with a bounded press-edge drain while Win32/native windows pump messages during a missing-code compilation pause. Deliver captured presses on resumed guest frames without modifying CPU state while stopped; old neutral and live host paths remain available.
- Linux generated native regressions passed; real Windows interactive Start-button acceptance has not passed.

## [0.2.0] - 2026-11-08

- **Changed:** - New generated NativeApp links a validated general-purpose loader and resolves translated instruction implementations from a shared module, while preserved legacy self-contained previews compile with `RD_SMS_HOT_TRANSLATION` unset. Real Windows display persistence during compilation remains unimplemented.
- **Validation:** Native and generated Z80/SMS synthetic tests run on Linux; Win32 genuine ROM recovery, display continuity and compiled controller orchestration remain unverified.
- **Compatibility:** Versioned module ABI and legacy static runtime path are retained; prior CPU semantics and historical source unchanged. Same-compiler SMS State C++ ABI only; live automatic compilation remains BLOCKED.

## [0.1.1] - 2026-11-07

- **Changed:** An exact guest VDP device frame count is emitted in the final native application report independently of the host output frame count and last sampled instruction/frame event.
- **Validation:** Source-attested Linux generated native application smoke exercises the terminal JSON fields; full Windows preview and independent hardware clock-difference verification are pending.
- **Compatibility:** Does not change the independent runtime host DLL ABI, machine/video provider interface, original CPU execution, or original 642 frozen source files.

## [0.1.0] - 2026-11-05

- **Changed:** Added independently versioned monitor/host orchestration as a reusable, non-game-specific service.
- **Validation:** Generic broker and token tests, source staging checks, compiled native synthetic guest with controller event emission. Independent Windows GUI display must be verified by owner.
- **Compatibility:** Preserves the compiled controller v0.4.4, unchanged host DLL and CPU/video plugins, generated Z80 code and all 642 frozen historical files.
