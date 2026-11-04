# RecompDev v0.4.0.7 — Native Frame & Interrupt Recovery

This is the COMPLETE Workbench distribution based on v0.4.0.6. The release advances the SMS/Z80 native C++ runtime. It is **not** a playable conversion of Shinobi; no real-ROM VBlank interrupt, correct game frame, or reference CPU/hardware parity has yet been demonstrated with v0.4.0.7.

## Installation (Windows PowerShell)

Close old Workbench, then:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.7-Native-Frame-Interrupt-Recovery.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.7\Run-Workbench.ps1'
```

Open `http://127.0.0.1:8777/execution`, select Shinobi, step budget 500,000 (or 1 million to extend), recovery attempts 2, click **Autonomously recover, compile & trace native C++**.

The launcher snapshots the v0.4.0.6 working catalogue first, preserving older versions. Keep v0.4.0.6 and v0.4.0.5 **evidence** directories: verified bank exports are reused only from known adjacent version roots, with all instruction hashes checked against the source ROM again.

## Implemented in this release

- Bounded approximate NTSC SMS frame scheduler: ~228 Z80 T-states/scanline, 262 scanlines/frame, sets VBlank status at scanline 192. Generated instruction T-state estimates are crude and intentionally **not cycle accurate**.
- VDP frame interrupt gating: requires VBlank status, VDP register 1 bit 5, Z80 IFF1 and completion of `EI`'s one-instruction latency. VDP status read clears the IRQ flag.
- Source-compiled interrupt entry to vector `0x0038`, stack push, IFF disable, and return through native generated Z80 instructions. IM0 assumes RST 38h bus data; IM2 fails closed with `IM2_INTERRUPT_VECTOR_NOT_MODELLED`. Experimental NMI entry at `0x0066` and `RETN` IFF1 restoration; user input/pause integration is not yet complete.
- `HALT` advances bounded **idle ticks separately from native instruction counts**, allowing VBlank IRQ to awaken HALT without falsifying native step counts.
- Trace `tstates`, estimated frame ticks, scanline, VBlank and IRQ events, VDP registers, VRAM/CRAM nonzero occupancy, `0xC001` reads/writes/last writer PC and nonzero transitions.
- Dump locally generated `hardware-state-vram.bin` (16 KB), `hardware-state-cram.bin` (32 bytes), and `hardware-state-vdp-registers.bin` (16 bytes) alongside every compiled job. These state dumps are **not** original ROM files and are not included in the release.
- Diagnostic preview PNG reports whether any pixels are nonblack. A nonblack preview is **not** evidence of a correct game frame.
- Workbench Native Execution page shows the new frame/IRQ/RAM-flag telemetry.
- Source SHA-256 verification, Ghidra bank overlay recovery, recompile/retry and bounded work queue preserved from v0.4.0.5/v0.4.0.6.

## Validation

A synthetic SMS fixture was compiled to actual native C++, enabled VBlank IRQ via VDP register 1, polled RAM `0xC001`, executed a compiled interrupt handler that set the RAM flag, returned, and exited the poll. Separate C++ tests cover `EI` latency, status clear, IM2 refusal and NMI stack behaviour. Existing native pilot, bank recovery and Workbench actions and bridge tests pass. None of these tests establish correct Shinobi instruction timing or CPU parity.

## First Windows Shinobi run

Look under:

`C:\Projects\RecompDev-v0.4.0.7\evidence\native-pilot-v0407\jobs\<job-id>\`

Upload `pilot-report.json`, `worker.log`, `execution.log`, and `diagnostic-background.png`, optionally the 3 hardware-state binary files if you want the VRAM/CRAM data analysed. Specifically inspect `maskable_interrupts`, `c001_nonzero_writes`, `last_c001_writer_pc`, `vblank_events`, `vdp_registers`, and the first native PC stop. If `maskable_interrupts=0`, DO NOT assume interrupts were correctly configured. If `c001_nonzero_writes=0`, DO NOT inject a synthetic flag; investigate the game's real handler and possible CPU/VDP timing errors.

## Known gaps

Independent full Z80 execution parity remains **NOT_TESTED**. Timing is approximate (not per-branch/per-instruction exact); real VDP scanline rendering, sprites, PSG synthesis, complete video hardware behaviour, controller/Pause-NMI wiring, some bank variants and input synchronization are not verified. IM2 intentionally stops rather than guessing an interrupt vector. First authentic native rendered frame / interactive gameplay are not established.
