# RecompDev v0.4.0.29 — Deterministic Windows browser-worker lifecycle

Full release based on v0.4.0.28. Fixes `test_native_preparation_v0403.py`
which previously invoked the owner's actual Ghidra installation for a synthetic
browser test and then gave up after roughly 12 seconds, leaving `worker.log`
held open on Windows (WinError 32). This was a regression harness defect, not
proof of an incorrect ROM or guest Z80 implementation.

## Behaviour and qualification

- Default native preparation continues to use real authenticated Ghidra analysis.
- `recomp.py ... serve --native-prepare-register-only` explicitly requests
  source-verified *registration only*. This is also useful without Ghidra,
  but cannot yield recovered instruction candidates. It is used for the
  deterministic browser integration fixture; no HTTP client can toggle it.
- The synthetic browser test still exercises local token/CSRF checks,
  source-bound registration, job result, path restrictions and worker report.
- Real Ghidra export ingestion stays covered by a separate authenticated
  fixture; genuine Ghidra/MAME parity is not established.
- The browser test uses a monotonic bounded wait and cancels any incomplete
  child worker before fixture cleanup; controller shutdown also reaps workers
  on a normal Workbench exit.
- The full Windows verification remains required on your own machine.

## Run on Windows

Extract `RecompDev-v0.4.0.29-Windows-Worker-Lifecycle.zip` into `C:\Projects`.
Run `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.29\Verify-v0429.ps1'`.
If it passes, initialise Workbench and run the same source-attested Shinobi
HEADLESS_AUTONOMOUS campaign, using the v0.4.0.29 catalogue and evidence root.

This release does not assert playable Shinobi, accurate Master System VDP/PSG,
full Z80 correctness or independent MAME execution alignment.
