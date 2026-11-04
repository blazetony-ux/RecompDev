# RecompDev v0.4.2 Windows Controller Hotfix 1

## Why the fix exists

On some Windows Python installations `py.exe -3` is not a suitable first choice for launching Python from `CreateProcessW`. The compiled RecompDev controller then exits with `Unknown option: -3` even though the preserved Python discovery and recovery services are installed correctly.

## Changes

Only `controller/main.cpp` and `harness/CMakeLists.txt` are changed, plus a new `controller/recompdev_python_config.h.in` build-time template. CMake supplies the exact Python3 interpreter path to the compiled Windows controller; standard `python.exe`, `python3.exe`, and finally `py.exe` remain fallbacks when process creation fails.

The existing 34 CTest cases include the plugin registry and direct-controller E2E tests that failed in the owner's Windows output. The original RecompDev v0.4.0.45 and harness v0.3 baseline trees and integrity manifest remain unchanged. The launcher change does not establish real-game runtime parity.

## Applying the one-file repair

Download `Repair-RecompDev-ModularMigration-v0.4.2-Windows.ps1` to Downloads, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\Repair-RecompDev-ModularMigration-v0.4.2-Windows.ps1"
```

The repair verifies the release identity and exact source SHA-256s before applying, backs up affected source files, rebuilds, and executes 34 CTest cases. It refuses unrelated or locally modified sources. It restores the originals if build/tests fail. Run `& "C:\Projects\RecompDev-ModularMigration-v0.4.2\RecompDev.exe" --plugins` after success.

The Windows repair itself cannot be executed within the Linux build environment. The patched source passed the 34-test Linux suite.
