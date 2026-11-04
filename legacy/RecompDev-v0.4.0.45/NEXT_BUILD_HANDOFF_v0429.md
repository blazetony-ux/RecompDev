# RecompDev v0.4.0.29 handoff

Windows v0.4.0.28 verification reached `test_native_preparation_v0403.py`;
the test timed out with real Ghidra unexpectedly engaged, and its live worker
held `worker.log` open while Python TemporaryDirectory tried to delete it.

New capability: explicit registration-only Workbench server mode, retaining
production Ghidra default. New lifecycle: cancellation on test failure,
normal server shutdown reaps worker processes. New gate verifies compiled
null-backend Z80, source-bound synthetic browser action, and portability checks.

The first authentic next milestone remains complete Windows verification,
then Shinobi source-authenticated integrated headless execution. Follow with
real Z80/MAME CPU/hardware divergence analysis, not further dashboard additions.
