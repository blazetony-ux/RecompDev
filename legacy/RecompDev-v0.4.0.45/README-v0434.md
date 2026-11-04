# RecompDev v0.4.0.34 — Cross-system Z80 platform assessment

This incremental release carries forward the complete v0.4.0.33 source tree and adds a read-only, data-driven separation of the reusable Z80 CPU from machine-specific hardware. It does NOT implement ZX Spectrum, MSX, CPC, ColecoVision or Game Gear native execution.

## What changed

* `platform_profiles/registry.py` defines distinct CPU, ROM layout, banking, ports, video and sound profiles for Master System, Game Gear, ZX Spectrum 48/128, MSX1, CPC464 and ColecoVision. Profiles are architectural metadata, not device implementations.
* `tools/Inspect-Z80-Platform.py` computes a source SHA256, records the basis for identification, assesses platform readiness, and returns exit 2 for blocked/unintegrated hardware. Sega 8-bit signatures are checked at conventional offsets. Filename extension alone cannot unlock Master System native execution. Explicit `--platform` is marked an owner assertion, not independent proof.
* `tests/test_platform_profiles_v0434.py` checks that a shared CPU does not imply a shared console, the Sega 8-bit distinction, and unverified/foreign hardware fail-closed behaviour.
* The native pilot project version changes to 0.4.0.34. Legacy native recovery, Ghidra, rendering and timing logic are carried forward without semantic changes.

## Usage on Windows

```powershell
$root='C:\Projects\RecompDev-v0.4.0.34'
py -3 "$root\tools\Inspect-Z80-Platform.py" --source 'C:\Roms\MASTERSYSTEM\Bank Panic (Europe).sms' --output "$root\platform-assessment.json"
py -3 "$root\tools\Inspect-Z80-Platform.py" --source 'C:\Roms\SPECTRUM\test.z80' --platform spectrum48 --output "$root\spectrum-assessment.json"
py -3 -m unittest discover -s "$root\tests" -p 'test_platform_profiles_v0434.py' -q
```

An exit code of 2 from the inspector means the native **hardware adapter is not qualified** (or the platform is not sufficiently identified), not that the Z80 instruction set itself is incompatible. Other `recomp.py` commands retain their existing capabilities and restrictions. The source file is never modified.

## Important limitations

The Z80 Ghidra export, P-code translation and native runtime remain Master System-specific in current integrated execution. Platform profiles do not create console-specific interrupt schedules, bank switching, VDP/ULA/PPIs, audio or boot loaders. Accurate independent reference parity and complete-game functionality remain **NOT ESTABLISHED**. Do not feed an arbitrary Z80 program into the SMS executor. A next substantive phase must implement a platform-neutral machine bus/device ABI with reference tests and a second system adapter.
