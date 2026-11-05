# state_observer — independent component history

## [0.1.0] - 2026-11-05

- **Changed:** Introduced a separately versioned generic state-observation component without changing existing runtime or game execution.
- **Added:** Versioned generic `MemoryRegionView` observation contract and read-only, bounded, delta-based per-sample recorder with explicit region metadata and multi-domain clocks. Machine-specific adapter files do not belong to the generic recorder.
- **Added:** Offline source-independent candidate-memory activity and directional correlation report. No game-specific player variable identification or correctness claim.
- **Validation:** Multi-region synthetic compiled C++ test; no-trace mode; signed byte delta / inconsistent chain rejection; unchanged original movement tests. Actual Windows Master System capture is pending.
- **Compatibility:** Existing controller, CPU plugin, runtime-host, video plugin, translated game code and historical baselines.
