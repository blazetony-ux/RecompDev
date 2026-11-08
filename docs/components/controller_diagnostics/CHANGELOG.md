# controller_diagnostics component history

## [0.1.2] - 2026-11-08

- **Changed:** Authenticated localhost subscription tracks bounded per-subscriber FIFO overflow and emits an explicit cumulative display-loss notice. The underlying native producer event log and controller job evidence are unaffected, and event payloads remain schema-checked and size-limited.
- **Validation:** Existing subscriber/authentication/overflow tests plus native monitor stress and end-to-end source-snapshot preview regressions.
- **Compatibility:** Same controller diagnostics v1 schema and read-only token authorization; never slows or controls guest execution, changes plugin semantics or asserts evidence completeness of ZIP excerpts.

## [0.1.1] - 2026-11-07

- **Changed:** Add one bounded native-result telemetry event type so the independently subscribed viewer can show final reported host and sampled guest frame counters without confusing the capture result with gameplay execution.
- **Validation:** Native preview regression exercises session end with a native-result event; invalid event types and oversized events remain rejected by the existing broker.
- **Compatibility:** No sockets exposed beyond authenticated loopback, no new mutation controls, and no CPU- or platform-specific payload parsing inside the controller.

## [0.1.0] - 2026-11-05

- **Changed:** Added independently versioned controller diagnostics api as a reusable, non-game-specific service.
- **Validation:** Generic broker and token tests, source staging checks, compiled native synthetic guest with controller event emission. Independent Windows GUI display must be verified by owner.
- **Compatibility:** Preserves the compiled controller v0.4.4, unchanged host DLL and CPU/video plugins, generated Z80 code and all 642 frozen historical files.
