# movement_trace — independent component history

## [0.2.0] - 2026-11-05

- **Changed:** Extended existing opt-in movement trace with a separately versioned generic `state_observer` memory-region provider interface. The Master System memory adapter publishes only guest work RAM; all generic differencing, schema validation and candidate correlation are console-independent. No player/ROM address is hardcoded.
- **Validation:** Synthetic multi-region/multi-clock compiled tests, original movement trace tests and immutability checks. Hardware accuracy, RAM player-variable identification, Windows session and reference-emulator parity remain unverified until owner evidence.
- **Compatibility:** Existing movement trace CSVs remain unchanged; `state-memory-*` files are additive. Compiled controller, CPU, video and host DLLs remain untouched.

## [0.1.0] - 2026-11-05

- **Changed:** Introduced a source-only, opt-in movement diagnostic adapter. It instruments disposable native-project copies at actual SMS controller-port read points and guest input delivery, and captures display R8/R9 scroll and raw sprite SAT positions at every rendered frame. The generic recorder is CPU-neutral; the Master System adapter owns port and VDP semantics. No input mappings or guest instructions were modified.
- **Validation:** Five focused tests cover strict source anchors, staging idempotence, immutable translated code, successful state correlation, deliberate wrong mapping and missing traces. Existing compiled native project smoke with diagnostics and 42 C++ regressions also pass in Linux. Windows Shinobi behavior remains to be evaluated using a new trace-enabled interactive run.
- **Compatibility:** v0.4.9.2 active controller, Z80 DLL, runtime-host DLL, SMS video DLL and all 642 protected historical files retain their original versions and hashes. The trace format is new and optional; it does not assert which sprite belongs to the player or prove gameplay parity.
