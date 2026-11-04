# RecompDev v0.4.3 — one-step Windows installation

Download and run `Install-RecompDev-ModularMigration-v0.4.3.ps1` directly from Downloads:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\Install-RecompDev-ModularMigration-v0.4.3.ps1"
```

The self-contained PowerShell script verifies an embedded source ZIP against SHA-256, extracts to `C:\Projects\RecompDev-ModularMigration-v0.4.3` (only if absent), checks the 642 original v0.4.0.45/harness files, compiles the C++ EXE and DLLs with MSVC, and runs 37 CTest gates. No manual ZIP extraction. Requires Visual Studio 2022 C++ Build Tools, CMake, Python 3; Ghidra is optional for installation but required for fresh real-ROM native preparation.

The existing v0.4.0.45, v0.4.1, and v0.4.2 installations are not touched. Existing v0.4.3 directories with a matching release marker are rebuilt/verified without source overwrite; other directories are refused. Windows build/installer remain unverified until run on the owner's machine.

**Direct RecompDev EXE:**

```powershell
& "C:\Projects\RecompDev-ModularMigration-v0.4.3\RecompDev.exe" --rom "C:\Roms\MASTERSYSTEM\Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms" --stage recover --steps 1000000 --frames 120 --max-recoveries 2 --max-rounds 3 --timeout 1200 --capture-hardware
```

**Review an earlier run without repeating native recompilation:**

```powershell
& "C:\Projects\RecompDev-ModularMigration-v0.4.3\RecompDev.exe" --analyze-evidence "C:\Projects\RecompDev-ModularMigration-v0.4.2\evidence\modular-v042\20261104T203712Z-73c59be7"
```

Use `--reference-image "C:\path\aligned-reference.png"` and optionally `--reference-session "C:\path\reference-session.json"` with either command for explicit comparisons. Reference images must be aligned and same-sized; a pixel match does not certify CPU, interrupt, audio, or gameplay parity.

Hardware review outputs PNG screenshots of captured terminal attempt images, PCM amplitude/silence diagnosis, a frame hardware CSV, JSON and Markdown summaries, and SMS tile atlases only if raw 16-KiB VRAM and optional 32-byte CRAM dumps exist. Frame hashes alone do not provide framebuffer images for every frame. `RECOMPDEV_EVIDENCE_ZIP` identifies the upload-ready archive.
