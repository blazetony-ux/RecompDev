# Input-driven native recovery (component `input_recovery`)

**Registry:** `workspace/components.json` lists `input_recovery` with scope `production-workflow`.

**Status:** Implemented as a separately versioned, source-only production workflow component, v0.1.0. Does not replace the existing controller, Z80 DLL, Master System machine or frozen P-code translator. Real owner-ROM progression beyond `0x7BE8` is **not yet independently verified**.

## Purpose and interfaces

- `runtime_host/guest_input_tap.py` and `runtime_host/bridge/rd_guest_input_tap.hpp` instrument **only** a disposable staged `interactive.cpp`, recording abstract logical button transitions at the actual guest CPU cycle. Neither `translated.cpp`, the original generator nor frozen historical files are modified.
- The existing preserved `RECOMP_INPUT_CYCLES_V1` CSV (`guest_cycle,port,buttons`) is the single deterministic input interface used by the compiled native game and original reset/replay recovery engine.
- `input_recovery/replay.py` safely ingests a previous native-runtime evidence ZIP, pins its ROM SHA-256 and selects **exact guest-cycle capture** if present. For older v0.4.8 captures containing only `elapsed_ms`, conversion requires an explicit machine clock and reports `HOST_MILLISECONDS_ESTIMATED`, not exact timing.
- `input_recovery/run.py` performs a bounded headless preflight against the **same existing generated game code**. Unless both the old stop address and status and the frame count (within two frames) reproduce, it stops before recovery and produces diagnostic evidence. If reproduced, it invokes the existing compiled `RecompDev.exe` with `--input-events`, source-verified coverage history, bounded recovery and unchanged production translation. The new game-code application may be built separately and retested.

## Windows commands

After applying workspace v0.4.9, recover using the latest previous matching native-run evidence ZIP:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\RecompDev\tools\Recover-Native-Input.ps1" -Rom "C:\Roms\MASTERSYSTEM\Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms"
```

For a specific previous run, supply `-EvidenceZip "C:\path\to\existing-evidence.zip"`. The PowerShell frontend supplies the Master System guest clock as a **machine-specific setting**, while the conversion core remains machine-agnostic. The prior run must still have its full external native-project evidence directory available; an upload ZIP alone does not contain compiled native project source.

To **record precise guest-cycle events** for subsequent replay, use the existing native launcher normally and press the game button. It now includes `guest-input-cycles.csv` in its evidence ZIP. The host's older wall-clock `input-events.jsonl` is retained for backward compatibility.

The update leaves `rd_runtime_host.dll` v0.1.0 untouched; the new source-only replay/bridge logic is tracked as `input_recovery` v0.1.0. Native game-code compilation remains incremental at the CMake target level; per-Z80-function incremental object compilation is **not** claimed.

## Evidence and safety

Output lives under `C:\Projects\RecompDev-Evidence\v0.4.9\input-recovery\<run-id>`, not Git. The manifest distinguishes exact versus estimated timing, actual guest stop reproduction, recovered attested instruction counts and guest progression. Reports can end with `REPLAY_NOT_REPRODUCED`, `INPUT_RECOVERY_BLOCKED`, `RECOVERY_ATTEMPTED_NO_CONFIRMED_ADVANCE` or `SOURCE_VERIFIED_RECOVERY_ADVANCED`; these do not imply playable gameplay. The original ROM, catalogue, legacy source, existing generated project and live installed DLLs are not overwritten. Native game builds remain outside Git.

**Validation:** Python tests in `input_recovery.tests.test_input_recovery`, staged native source-authentication fixture compilation, preserved native replay invocation and complete workspace CTest suite. The historical v0.4.8 Shinobi input event evidence contains 201 frames, a Z-button press, and a stop at `0x7BE8`; this specific run has only approximate wall-clock input timing, so a precise replay is not guaranteed.
