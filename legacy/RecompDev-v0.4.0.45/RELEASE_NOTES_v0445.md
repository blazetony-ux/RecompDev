# RecompDev v0.4.0.45 — Compiled test portability and Windows verification integrity

## Root cause of the Windows v0.4.0.44 verification failure

`tests/test_sms_psg_v0443.py` fell back to invoking `cl` when it found no
`g++`/`clang++`, while using GCC-specific `-std`, `-I`, and `-o` flags.
Windows installations may expose a working Visual Studio/MSVC compiler to
CMake without providing a callable `cl` command in the user's Python PATH.
The test therefore failed with WinError 2 before testing any PSG behaviour.

## Fix

- The mandatory compiled PSG fixture now builds through the CMake C++ toolchain
  (same compiler-selection mechanism as the passing native output check).
- Both single-config and multi-config executable layouts are supported.
- Compilation and execution failures are fatal with command details, never
  silently treated as passing skips.
- The fixture uses `Debug` configuration so C++ `assert()` checks are active.
- Independent unit tests cover `.exe` discovery, ambiguous/absent binaries,
  missing CMake, and the absence of direct `cl` fallback.
- The generated-frame test no longer accidentally exposes an imported test
  class to `unittest` discovery, which was causing unnecessary duplicate runs.

## No gameplay/CPU-engine changes

Preserves 0.4.0.44 recovery cache, SQLite lifecycle fixes, sound synthesis,
input, native host and existing shared catalogue unchanged. Does not delete or
migrate `RecompDev-Data/catalogue.sqlite` or
`RecompDev-Data/verified-coverage-v0443.sqlite`.

## Qualification and limitation

Local CMake compiled PSG fixture and portability checks are required before
publishing. Authentic Windows deployment and game-specific R-Type, PSG audio,
and emulator parity remain independently unverified until owner acceptance.
