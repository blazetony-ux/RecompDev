# RecompDev Modular Harness v0.1.1 fix

- **Fix:** `tests/test_sidecar.py` uses `contextlib.closing(sqlite3.connect(out))` instead of relying on the SQLite transaction context to release a Windows file handle.
- **Regression check:** verifies output DB can be explicitly deleted, detecting retained handles prior to temporary directory cleanup.
- **Scope:** no modifications to harness C++, plugin DLLs, ABI, main RecompDev 0.4.0.45, discovery exporter, or production catalogue.
- **Validation:** Linux CMake build and CTest 12/12 passed. Windows MSVC user build previously compiled v0.1; v0.1.1 requires rerunning CTest on Windows.

For an existing Windows v0.1 folder, replacing only `tests/test_sidecar.py` is sufficient, then run `ctest --test-dir build-win -C Release --output-on-failure`.
