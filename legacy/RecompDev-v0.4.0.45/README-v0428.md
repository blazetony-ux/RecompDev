# RecompDev v0.4.0.28 — Windows full-regression portability

This is a **complete, separately numbered** release derived from v0.4.0.27.
It fixes the three failures reported during the owner Windows `test_blockers_v032.py` run:

1. The cache-import test leaked `working.sqlite` through Python's transaction-only
   SQLite context manager. It now closes SQLite connections explicitly. A static
   test also guards against recurrence across the existing test fixtures.
2. The ROM argument test hard-coded POSIX `/` separators instead of comparing
   the actual host-platform path that RecompDev forwards.
3. Ghidra source-cache recovery was tested as though its compiler smoke status
   were stable on all machines. Cache/source-authentication testing now uses an
   explicitly unavailable compiler and checks generated C++ and precise
   `COMPILER_NOT_FOUND` status. The **real compiled Z80 null-host tests remain
   mandatory** in `Validate-v0428.py` and the full verification suite.

For preventative Windows hygiene, the remaining temporary SQLite connection
contexts in the test suite and the durable-campaign prepared-input reader have
been changed to explicit closures. None of the guest CPU, video, audio, input,
ROM recovery, hardware semantics or independent-reference evidence claims
have been altered.

## Windows commands

- Extract `RecompDev-v0.4.0.28-Windows-Full-Regression.zip` to `C:\Projects`.
- Verify `C:\Projects\RecompDev-v0.4.0.28\Verify-v0428.ps1`.
- Run Workbench with `C:\Projects\RecompDev-v0.4.0.28\Run-Workbench.ps1`.
- After complete Windows verification, initialise the new catalogue once and
  run a single `HEADLESS_AUTONOMOUS` integrated Shinobi campaign.

## Qualification boundary

Compiler acceptance remains synthetic. Master System hardware parity, MAME
alignment, fully verified Z80 semantics and playable Shinobi remain open.
