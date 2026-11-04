# RecompDev v0.4.0.39 — Native Screen & Correctness Foundation

**Engineering release with limited acceptance, not completion of the previously proposed full v0.4.0.39 Master System correctness milestone.** This is a full isolated install with the v0.4.0.38 conditional CALL/RET and TH-line fixes retained. No ROM, game-specific C++ translation, generated game executable or emulator payload is included.

## Display an authentic generated native framebuffer

The native frontend already uses `hardware/core.hpp` (CPU-neutral 4096×4096-bounded `Frame` in BGRA8888), `hardware/win32_window.hpp` (Win32 presentation), a Master System adapter, and `RecompDevNativeApp` generated from source-attested Z80 instructions. Prior captures saved only the last native frame as `native-frame.ppm`, normally hidden in job evidence. This release adds a ROM SHA-verified launcher, an on-screen display, and a retained capture image.

1. Close the previous Workbench. Extract the distribution ZIP into `C:\Projects` with its top-level directory intact.
2. `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.39\Verify-v0439.ps1'`
3. `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.39\Run-Workbench.ps1'`
4. **No new conversion required to view existing Shinobi output** (if the v0.4.0.38 seven-game campaign retained its `native-project/build` tree):
   `py -3 'C:\Projects\RecompDev-v0.4.0.39\tools\View-Native-Output-v0439.py' --game shinobi`
5. The window shows frames emitted by translated Shinobi instructions. Close with Esc. If using a v0.4.0.38 compiled app, a separate PPM viewer appears when the native session finishes because the older app cannot hold its window open. New v0.4.0.39 compiled apps display a `capture complete` title and hold the last generated frame until Esc or a 300-second guard.
6. The launcher prints `FRAMEBUFFER=` and `REPORT=`. They are saved under `evidence\native-screen-v0439\<game>\<timestamp>\` in the new installation; ROM remains in the original location.

Use `--game bank-panic`, `--game alex-kidd`, `--game fantasy-zone`, `--game r-type`, `--game sonic-sms` or `--game wonder-boy` for other recovered campaigns; incomplete translation or black output may still occur. `--still` opens an already captured PPM without running the CPU. `--no-hold` closes after the session. `--frames 120` is the default.

After running the full revised campaign, the launcher preferentially selects the latest source-matched v0.4.0.39 project. To run it:

`py -3 'C:\Projects\RecompDev-v0.4.0.39\tools\Run-SMS-Campaign-v0439.py'`

The latest complete compiled campaign source must remain in the original installation's `evidence` folder. ZIP summary uploads alone do not include the executables. The launcher verifies source SHA against ROM and generation evidence, the recorded native pilot binary hash and, for v0.4.0.39 campaigns, the additional graphical executable hash.

## General translator changes

- Add generic Ghidra `INT_SRIGHT` lowering and source-width-correct sign propagation; covers positive, negative, oversized, 8/16/32/64-bit cases without relying on signed right-shift implementation behaviour.
- Preserve the conditional CALL/RET and SMS TH control changes from v0.4.0.38.
- Save the `RecompDevNativeApp` digest in new continuous recovery reports (previous v0.4.0.38 reports hashed only the companion diagnostic executable).
- Correct the v0.4.0.39 campaign's release identity and use its own working catalogue.
- Provide Windows last-frame hold functionality only in generated v0.4.0.39 apps; this does not advance guest execution or invent pixels.

## Qualification and explicit limitations

Locally passed: compiled image/PCM fixture, compiled conditional CALL/RET tests, compiled TH-feedback tests, compiled arithmetic-right-shift cases, five native-screen and provenance regressions, v0.4.0.38/v0.4.0.37 release contract checks, bridge suite (15 tests, one pre-existing skip), and release ZIP hash integrity. **Full repository suite and inherited nested release acceptance did not finish within the local execution budget; no full-suite pass is claimed.** No Windows GUI run was possible in the Linux packaging environment. No new seven-ROM authentic-game campaign was run locally because six of the seven ROMs reside on the owner's Windows machine.

Outstanding: reference CPU/state divergence diagnosis; Shinobi MAME parity and playability; complete SMS video and sound accuracy; R-Type post-shift progression; Sonic SMS execution failure; generic self-directed fault correction; independent program equivalence; cross-ISA architectural proof. The existing `hardware` frame contract is architecture neutral, but the graphical live game bridge is currently integrated only for the Master System/Z80 pilot. This does not qualify Mega Drive, PlayStation or other system display output.
