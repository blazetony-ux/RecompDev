# runtime_host_integration component history

## [0.1.1] - 2026-11-07

- **Changed:** An exact guest VDP device frame count is emitted in the final native application report independently of the host output frame count and last sampled instruction/frame event.
- **Validation:** Source-attested Linux generated native application smoke exercises the terminal JSON fields; full Windows preview and independent hardware clock-difference verification are pending.
- **Compatibility:** Does not change the independent runtime host DLL ABI, machine/video provider interface, original CPU execution, or original 642 frozen source files.

## [0.1.0] - 2026-11-05

- **Changed:** Added independently versioned monitor/host orchestration as a reusable, non-game-specific service.
- **Validation:** Generic broker and token tests, source staging checks, compiled native synthetic guest with controller event emission. Independent Windows GUI display must be verified by owner.
- **Compatibility:** Preserves the compiled controller v0.4.4, unchanged host DLL and CPU/video plugins, generated Z80 code and all 642 frozen historical files.
