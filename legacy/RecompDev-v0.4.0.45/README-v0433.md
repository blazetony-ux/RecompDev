# RecompDev v0.4.0.33 — Z80 Timing, SMS Scanline Counter & Reference-Startup Assessment

This release **implements a portion** of the proposed ten-milestone Z80 programme, not all ten.

## Substantive changes, no game-specific patches

- The generator emits source-opcode-driven Z80 T-state accounting: conditional JR/DJNZ, CALL/RET, CB and ED groups, DD/FD-prefixed registers and indexed displacement, repeated block operations. Unsupported/ambiguous opcode timing remains explicitly **unqualified**, using the older estimate for continued diagnostics. Timing calculation copies the instruction bytes **before** performing guest memory writes, so a bank switch during an instruction cannot change its decoding.
- The SMS device reads V-counter from mirrored 0x40-0x7E read ports. For NTSC 192-line mode, it uses the documented `00–DA,D5–FF` sequence (262 lines) rather than returning zero. Ports 0x7F/odd mirrors return a held H-counter latch, updated on software-driven TH rising edges. H latch phase is approximate. The general guest bus still handles VDP/PSG/mapper events; null video/audio do not disable it.
- The native pilot and continuous host report decoded/estimated timing counts and V-counter reads. This makes an authentic second run diagnostic, rather than repeating the old 500,000-instruction experiment without new data.
- Source-authenticated selected-I/O comparison of prior MAME and native captures, via `tools/Assess-SMS-Startup-v0433.py`. It validates the MAME file hash and every candidate event chunk; an initial selected I/O difference is **not** mislabelled a CPU parity error when boot paths/initial states have not been aligned. Legacy owner evidence yields `FIRST_IO_DIFFERENCE_WITH_UNALIGNED_START` and zero matching PSG/VDP-control writes.
- Compiled C++ fixtures cover Z80 instruction cycle cases, SMS V-counter wrap, stable H-counter latch, a *second* Z80 program's real translated scanline wait loop, and both existing Z80 and M68000/MIPS regression suites.

Documentation for NTSC SMS counter sequence: https://www.smspower.org/Development/ScanlineCounter .

## Windows commands

Install:

`Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.33-Z80-Hardware-Correctness.zip" -DestinationPath 'C:\Projects' -Force`

Verify:

`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.33\Verify-v0433.ps1'`

Workbench:

`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.33\Run-Workbench.ps1'`

After verification and Workbench initialisation, close Workbench with Ctrl+C and run an integrated native campaign **with the changed timing and counter model**:

`$r='C:\Projects\RecompDev-v0.4.0.33'; py -3 "$r\tools\Run-Integrated-Native.py" --db "$r\catalogue.v0433-working.sqlite" --source-id 'dac4f1dcb41193cb42a96950444a87c5f2952ea66474c59a38c07b10ac411e47' --rom-root 'C:\Roms' --output-root "$r\evidence\integrated-native-v0433\jobs" --steps 500000 --frames 120 --recoveries 2 --mode HEADLESS_AUTONOMOUS`

## What remains unqualified

No automatically corrected first MAME CPU divergence has been established. BIOS/cartridge boot, frame phase, initial hardware state, undocumented/unknown opcode timing, IRQ/IM2, accurate H-counter pixel phase, accurate Master System sprites, frame timing and PSG noise remain open. No complete-game recovery/playability claim. On an unseen Z80 game, unsupported semantics stop explicitly; new console-specific hardware still needs adapters. Previous M68000/MIPS restricted native backends are retained, with no change in their authentic-game qualification.

When reporting a new run, include `timing_qualified_steps`, `timing_unqualified_steps`, `vcounter_reads`, `first_vcounter_read_step`, first hardware events and whether CRAM changed. An improved frame or increased step count alone cannot establish correctness.
