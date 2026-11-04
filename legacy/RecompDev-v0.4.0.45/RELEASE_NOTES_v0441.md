# RecompDev v0.4.0.41 — Native Start/Pause & Input Replay

## What changed

- The Sega Master System console Pause/Start switch is represented as an edge-triggered Z80 NMI at vector 0x0066, not as an extra controller DC/DD bit. The CPU-neutral button::Start input is interpreted by the SMS adapter, and guest cycles are accounted for at the next translated instruction boundary. Holding Enter does not continuously retrigger an NMI.
- Both live Win32 keyboard Enter and deterministic guest-cycle input replay use the same console input path. Arrows, Z and X continue to map to controller directions and buttons.
- A new `tools/Test-Native-Interaction-v0441.py` rebuilds *existing source-attested owner-generated game code* with the v0441 host/console adapter; it never modifies the prior generated project, the ROM, shared catalogue, or guest translation. It runs a neutral comparison and a scripted Start press, reports guest NMI count and first framebuffer difference, and packages bounded evidence.
- `tools/Run-SMS-Campaign-v0441.py` remains available for a complete native regeneration, with a real v0.4.0.40 baseline comparison. No full seven-game rerun is required to perform the focused R-Type Start experiment.
- `Verify-v0441.ps1` adds compiled NMI/edge/scheduler tests and harness provenance/input-timing tests to the existing CPU/framebuffer/bridge acceptance.

## Owner-side R-Type interaction test

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-0441.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.41\Verify-v0441.ps1'
py -3 'C:\Projects\RecompDev-v0.4.0.41\tools\Test-Native-Interaction-v0441.py' --game r-type --start-frame 300 --frames 600 --show
```

The tool prints `EVIDENCE_ZIP=...` even if guest execution hits a new code-coverage boundary. The default Start pulse is four frames, scheduled by guest Z80 cycles. The `--button a` and `--button b` alternatives can independently probe games that use a controller button to leave their title screens; neither is treated as the console Pause NMI. `--mode live --frames 1800` instead allows the Win32 host window to receive live Enter/arrow/Z/X keys.

## Qualifications

- An image or input-driven frame difference is **not** evidence of gameplay or pixel parity with MAME.
- A Start-triggered NMI can immediately uncover untranslated code at 0x0066; if so, that is a *new verified recovery target* rather than permission to emulate/hardcode the missing guest code.
- The v0440 seven-game performance baseline remains the only independently observed commercial-game campaign; v0441 owner-side Windows interaction has not yet been run.
- Live input is polled periodically by the native host, and frame/audio hardware fidelity remains experimental. Authentic-game commercial WAVs remained silent in v0440 evidence; not resolved by this input release.
- R-Type's source-attested C++ is compiled only on the owner's computer and not shipped in this ZIP. The shared persistent catalogue is reused directly.
