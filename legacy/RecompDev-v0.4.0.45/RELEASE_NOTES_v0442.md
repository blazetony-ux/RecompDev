# RecompDev v0.4.0.42 — Verification Correction & Native Interaction

This is a **new uniquely numbered release** correcting a v0.4.0.41 verifier packaging mistake. The v0441 verifier references three nonexistent test files (`test_windows_native_stack_v0441.py`, `test_native_process_exit_v0441.py`, `test_staged_recovery_v0441.py`), whereas the real tests remain named v0440. Python unittest returns success for zero discovered tests, so the original verifier aborted after the first pattern due to an empty run.

The v0442 verifier references the real tests and runs a new **fail-closed discovery preflight** requiring that every selected pattern match a file and discover at least one test. Additional regression tests intentionally exercise absent and empty selections. All source-attested Start/Pause NMI, neutral/replay, host stack and device/runtime code remain unchanged from v0441 except the release version metadata and versioned owner-tool entrypoints. Historical regression tests continue to run.

There is no database migration or copy. The existing central catalogue remains `C:\Projects\RecompDev-Data\catalogue.sqlite`.

## Owner verification

1. Extract `RecompDev-0442.zip` to `C:\Projects`.
2. Run `Verify-v0442.ps1`.
3. Run `tools/Test-Native-Interaction-v0442.py --game r-type --start-frame 300 --frames 600 --show`.
4. Upload the printed `EVIDENCE_ZIP` even if input-triggered execution reaches another source-verified recovery boundary.

Authentic Windows gameplay, correct audio and reference parity are **not established** by synthetic regression tests.
