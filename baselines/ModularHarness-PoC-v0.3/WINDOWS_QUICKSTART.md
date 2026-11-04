# Windows quick start

Requirements: 64-bit Windows 10/11, Visual Studio 2022 Build Tools with **Desktop development with C++** (MSVC and Windows SDK), and CMake on PATH. Python 3 is optional for semantic report tests and the catalogue sidecar importer.

Unzip into an **independent** directory, e.g. `C:\Projects\RecompDev-Harness-PoC-v0.1.1`. Do NOT overwrite or merge into `RecompDev-v0.4.0.45`.

```powershell
cd 'C:\Projects\RecompDev-Harness-PoC-v0.1.1'
powershell -NoProfile -ExecutionPolicy Bypass -File .\Build-Windows.ps1
.\build-win\bin\Release\RecompDevHarness.exe --list
.\build-win\bin\Release\RecompDevHarness.exe --validate --out .\build-win\reports\manual
.\build-win\bin\Release\RecompDevHarness.exe --machine rd_machine_synthetic --validate --out .\build-win\reports\alternate
```

The script configures CMake, compiles one `RecompDevHarness.exe` and 8 independent DLLs, then runs CTest. **These Windows binaries have not been compiled or exercised in the author's Linux environment.** If there are compiler errors on your PC, retain the CMake output and test log; do not interpret the Linux result as a Windows pass.

Do not point the harness at real game ROMs yet. The fixture is currently embedded author-created bytes and is used only to qualify the architecture. The initial generated `rd_game_fixture.dll` is not RecompDev's Ghidra-derived `translated.cpp` output.

## Windows SQLite cleanup fix (v0.1.1)

The original Windows build compiled successfully but test 12 failed during TemporaryDirectory cleanup because the test used `with sqlite3.connect(...)` without closing the SQLite connection. v0.1.1 wraps the connection in `contextlib.closing(...)` and verifies that its `.sqlite` file can be unlinked. To test without recompiling: `ctest --test-dir build-win -C Release --output-on-failure`.
