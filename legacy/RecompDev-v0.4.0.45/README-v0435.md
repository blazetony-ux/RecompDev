# RecompDev v0.4.0.35 — Corrective continuous recovery and hardware triage

## What is implemented

- Master System native continuous host now exposes final **PC, physical cartridge offset, mapper state, CRAM nonzero bytes, bank switches and IRQ counters**. When translated C++ encounters unmapped code, its native status distinguishes initial from banked missing code using actual mapper state.
- `tools/Run-Continuous-Recovery-v0435.py` authenticates a Ghidra Z80 export and owner ROM, generates the C++ project, compiles it, executes the continuous host, recovers newly reached missing physical-ROM instructions using the owner-installed Ghidra SMS adapter, **regenerates and recompiles**, then **replays from reset** using the same ROM and optional input replay. Every new export is source-byte attested; recovery is bounded, has cycle/step caps and fails closed on duplicate, unsafe or unsupported code. Session, executable and source hashes are recorded in `continuous-recovery-report.json`.
- `tools/Diagnose-Z80-Hardware-v0435.py` produces cautious PC/register/mapper/IRQ/CRAM evidence triage from an existing pilot report, optionally joined to an independent hash-matched MAME selected-I/O alignment report. It never treats unaligned startup divergence as a proven CPU defect.
- `Verify-v0435.ps1` restores the complete integrity, compiled acceptance, core regressions and bridge verification sequence. Historic version tests no longer hard-pin obsolete active versions. Workbench migration considers v0.4.0.34/v0.4.0.33 owner catalogues.

## Install — Windows PowerShell (close old Workbench first)

1. Extract:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.35-Corrective-Recovery.zip" -DestinationPath 'C:\Projects' -Force
```

2. Run full verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.35\Verify-v0435.ps1'
```

3. Launch Workbench:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.35\Run-Workbench.ps1'
```

## Independent continuous-recovery operator test

The new script requires `--rom`, either `--db` (working catalogue containing a source-attested export) or `--export` (initial Ghidra P-code export), and a *new empty* `--output-dir`. Example for a prepared Bank Panic ROM:

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.35\tools\Run-Continuous-Recovery-v0435.py' --rom 'C:\Roms\MASTERSYSTEM\Bank Panic (Europe).sms' --db 'C:\Projects\RecompDev-v0.4.0.35\catalogue.v0435-working.sqlite' --output-dir 'C:\Projects\RecompDev-v0.4.0.35\evidence\bank-panic-v0435' --frames 120 --steps 2000000 --max-recoveries 3
```

The script uses an owner-supplied Ghidra installation when code recovery is required. It DOES NOT run autonomous recovery from the GUI. The CLI resolves prepared Ghidra source evidence from the working database when `--db` is provided; alternatively specify `--export`. It preserves no original ROM bytes in the packaged release. On failure, attach `continuous-recovery-report.json` plus logs from the affected attempt, excluding proprietary ROMs. Existing pilot `recovery` functionality is separate and unchanged.

## Hardware triage

```powershell
py -3 'C:\Projects\RecompDev-v0.4.0.35\tools\Diagnose-Z80-Hardware-v0435.py' --pilot-report 'C:\PATH\TO\pilot-report.json' --output 'C:\PATH\TO\new-hardware-triage-v0435.json'
```

Optionally supply `--alignment-report` with an existing hash-matched MAME/native selected-bus report. Current Shinobi startup parity, aligned CPU/IRQ checkpoints, CRAM initialization and playable gameplay remain **not established**.

## Release acceptance

The compiled synthetic Z80 fixture proves that missing code can cause a stop and that verified recovery can regenerate, compile and replay with an increased instruction budget. Authentic Bank Panic past 99 frames, Alex Kidd past 66 frames and Shinobi parity are **not tested in the package environment**. Native hardware is still experimental, and only Master System has an integrated execution/recovery provider. No game-specific fixes were added.
