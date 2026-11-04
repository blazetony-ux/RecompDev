# RecompDev v0.4.2 — compiled controller direct execution

The user-facing command is **RecompDev.exe**. `RecompDevHarness.exe` remains the separate DLL execution test harness; it is NOT the real-ROM discovery/recovery controller.

After running the one-file installer, run directly in **one PowerShell line**:

```powershell
& "C:\Projects\RecompDev-ModularMigration-v0.4.2\RecompDev.exe" --rom "C:\Roms\MASTERSYSTEM\Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms" --stage recover --steps 1000000 --frames 120 --max-recoveries 2 --max-rounds 3 --timeout 1200 --capture-hardware
```

- `--auto-continue` is ON by default for `recover`. It permits up to **three** bounded original recovery runs against the same source-verified coverage cache. Override with `--max-rounds 1..12` or disable with `--no-auto-continue`.
- `--max-recoveries` controls the number of verified recovery passes *within each round*. There is no unbounded loop. `--timeout` limits the total recovery rounds in seconds. Discovery and native preparation each have their own timeout.
- `--out DIR` selects a new evidence folder; existing destinations are rejected. Without it each run creates an isolated timestamped folder below `evidence/modular-v042`.
- `--catalogue PATH` selects a source SQLite database; it is copied using the SQLite backup API into a new working database. Source and original ROM are SHA-256 checked before/after the workflow.
- `--ghidra PATH` optionally specifies a Ghidra executable; `--export PATH` supplies an authenticated Ghidra-format export.
- `--plugins`, `--verify`, `--status`, `--version` query available information. `RecompDev.exe --help` prints usage.

## The executable's implementation boundary

`RecompDev.exe` is a **real compiled C++ controller** which parses the top-level entry command and launches the preserved Python `modular/cli.py` via native process APIs, with arguments passed directly (no PowerShell or shell interpolation). The Python controller invokes the actual unmodified v0.4.0.45 discovery, Ghidra preparation, native compilation/recovery and coverage-cache services through registered adapters. It does **not** pretend that Python, Ghidra or other original tools were converted into C++ DLLs. The architecture can replace these service adapters separately after independent parity tests.

## Recovery continuation and diagnostics

Under the evidence folder, `recovery/continuous-recovery-report.json` aggregates per-round attempts; `recovery/round-XX/continuous-recovery-report.json` preserves each original report. `recovery-stage/round-XX/` holds each service log. The controller's `legacy_native_steps`, `maximum_frames_observed`, `recovered_entries`, `recovery_rounds` and `recovery_stop_reason` fields are populated from the actual reports.

A `RECOVERY_BUDGET_EXHAUSTED` result with new source-attested code can trigger another bounded round. A repeated stop without additional execution progress or a round with no new attested instructions stops. `STEP_BUDGET_REACHED` is classified separately as an execution budget limit; no automatic additional recovery is asserted. Native-only correctness and gameplay parity are **not established** by frame counts or instruction counts alone.

When capture is enabled the report includes raw VDP/PSG write counts, nonzero CRAM bytes, nonzero audio samples, frame-hash counts and maskable interrupt observations. It flags silent audio despite PSG writes and very low interrupt counts for **review**, not as proof of a defect or a corrected game.

## Preservation

The original RecompDev v0.4.0.45 files and original modular-harness v0.3 files remain unchanged and checked against the existing 642-file SHA-256 preservation manifest. The original standalone installations and external `RecompDev-Data` are not changed. Owner-ROM native gameplay and Windows installation still require user-machine qualification.
