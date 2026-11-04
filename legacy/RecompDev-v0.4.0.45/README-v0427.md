# RecompDev v0.4.0.27 — Cross-platform batch verification correction

## What this release fixes

v0.4.0.26 passed Windows native null-host acceptance, then full regression stopped in `test_batch_campaign.py`: a test created a POSIX `chqdev-linux-amd64` shell script while production expects `chqdev-windows-amd64.exe` on Windows. v0.4.0.27 replaces the executable fixture with a platform-matched **mocked subprocess boundary**. It still checks source SHA-256 before execution, production Go path selection, bounded timeouts, manifest schemas, manifest-source identity, and failed backend handling. No real Go executable is bundled and these simulated tests do not qualify native conversion.

## Windows setup

- Extract ZIP to `C:\Projects` and run `C:\Projects\RecompDev-v0.4.0.27\Verify-v0427.ps1`.
- Workbench: `C:\Projects\RecompDev-v0.4.0.27\Run-Workbench.ps1`.
- After full Windows verification, run one integrated Shinobi campaign with `tools/Run-Integrated-Native.py`, source-authenticated, bounded steps/frames/recoveries, mode `HEADLESS_AUTONOMOUS`.

## Validation boundary

`test_batch_campaign` now mocks only the external subprocess and not source/manifest checks. The Ghidra native-preparation Python fixture is also invoked through the Python interpreter on Windows without altering the real Ghidra command path. This is not a Go binary test, CPU parity, verified MAME alignment or gameplay. Authentic gates remain open. The release still contains all v0.4.0.26 Windows fixes, as well as the shared generic null video/audio/input adapters.
