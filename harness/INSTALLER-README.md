# RecompDev Modular Harness v0.2 — installer add-on

The original v0.2 source, host, plugin code, production translator bridge, and tests are unchanged. This add-on restores a one-command **isolated Windows installer**.

## One-step install from the bundled archive

Extract `RecompDev-ModularHarness-PoC-v0.2.1-OneStep-Windows.zip` into any temporary folder, then from PowerShell in that folder run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-ModularHarness-Windows.ps1
```

The installer verifies the original source ZIP SHA-256, extracts it to `C:\Projects\ModularHarness-PoC-v0.2`, builds the host and DLLs with MSVC, runs all 18 CTest tests, and verifies key outputs. Requires Visual Studio 2022 C++ Build Tools, CMake and Python 3 (`py -3`). **No administrator rights or network download are required**. The existing `RecompDev-v0.4.0.45` tree is not accessed or modified. If the destination already has PoC source, it builds there without overwriting source files. Other existing directories are rejected rather than overwritten.

After success:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Projects\ModularHarness-PoC-v0.2\Run-Sample-Windows.ps1
```

## If you already extracted v0.2 source

Copy `Install-Windows.ps1` and `Run-Sample-Windows.ps1` from the installer add-on ZIP into your existing `ModularHarness-PoC-v0.2` directory, then run `powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Windows.ps1`. It detects the local source and builds/tests **in place**, with no source replacement.

## Other options

Use `-InstallDir 'D:\Projects\ModularHarness-PoC-v0.2'` for a new isolated location, `-SourceZip 'D:\Downloads\RecompDev-ModularHarness-PoC-v0.2-Source.zip'` for a separately downloaded source archive, or `-SkipBuild` to install source only (unverified). The default installation does not add PATH entries, register services, install drivers, overwrite existing unrelated directories, touch your original RecompDev repo, or fetch anything from the Internet.

**Validation note:** this installer is authored for Windows PowerShell 5.1+ and has not been executed on Windows in the authoring environment. The unchanged v0.2 project was previously built and tested on Linux (18/18 GCC and Clang). Windows compiler/test outcome must be confirmed locally.

Source ZIP SHA-256: `4f25a95b0b382540e2c8c2913b0f2f9b7b4caa7e9ea27e1ac5e454b8da48b603`
