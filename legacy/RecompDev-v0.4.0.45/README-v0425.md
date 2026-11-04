# RecompDev v0.4.0.25 — Universal Null Host Backends

## Purpose
Explicitly select Null / Capture / Window video, Null / Capture / Speaker
PCM and Neutral / Replay / Live controller inputs at the **PC host boundary**.
This allows source-authenticated native conversion campaigns to run without
physical display/audio/input peripherals while retaining the guest's VDP,
PSG, controller ports, CPU code, interrupts and cycle progression.

The null sinks currently **consume fully generated frames and PCM** then
throw their content away. They do not skip device timing or declare inaccurate
hardware to be correct. They remove physical-device and evidence-storage
dependencies, not necessarily the CPU cost of rendering/synthesis.

## New interfaces

- `hardware/backends.hpp`: `NullVideoSink`, `NullAudioSink`,
  `NeutralInputSource`, `ReplayInputSource`, generic backend enums/parsers.
- Generated source-authenticated `RecompDevNativeApp`: run without attached
  host devices using `--mode HEADLESS_AUTONOMOUS` or independent
  `--video null|capture|window`, `--audio null|capture|speaker`,
  `--input neutral|replay|live`, `--input-events <CSV>`.
- `tools/Run-Continuous-Native.py`: Python source-bound launcher validates
  backend claims, null accounting and final guest fingerprint.
- `tools/Run-Integrated-Native.py`: integrated conversion and two deterministic
  null runs, plus **one capture control** to compare guest CPU/memory,
  hardware-write counts, cycles and stop boundary (unless `--no-repeat`).
- Source-linked Workbench remains read-only; first launch snapshots the existing
  v0.4.0.24 working catalogue into `catalogue.v0425-working.sqlite` without
  modifying previous installs.

## Windows installation

1. Expand full archive into `C:\Projects`, creating `RecompDev-v0.4.0.25`.
2. Full verification: `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.25\Verify-v0425.ps1'`
3. Workbench: `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.25\Run-Workbench.ps1'`

## Shinobi owner test

Launch Workbench once to initialise the working catalogue, then close it with
Ctrl+C. Run the **same source-authenticated integrated workflow** without
physical output, using your already registered owner ROM:

```powershell
$r='C:\Projects\RecompDev-v0.4.0.25'; py -3 "$r\tools\Run-Integrated-Native.py" --db "$r\catalogue.v0425-working.sqlite" --source-id 'dac4f1dcb41193cb42a96950444a87c5f2952ea66474c59a38c07b10ac411e47' --rom-root 'C:\Roms' --output-root "$r\evidence\integrated-native-v0425\jobs" --steps 500000 --frames 120 --recoveries 2 --mode HEADLESS_AUTONOMOUS
```

Use the included Python command to capture any resulting `campaign-result.json`
and `continuous-session.json` output, and zip the job excluding `native-project`
if sharing. The **null mode deliberately emits neither PPM nor WAV** during the
main run, but `host-capture-control` may contain diagnostic PPM/WAV from the
required differential test. This control is a consistency check, not a MAME
oracle. Missing translated code, missing authentic hardware, MAME discrepancies
and unimplemented CPU semantics remain blockers.

## Qualification

Two original author-created Z80 fixtures and one unrelated synthetic machine
are tested with capture and null sinks. This is not independent authenticity
parity. This release does not assert playable Shinobi, fully correct Z80, a
qualified Master System VDP/PSG/IRQ model, or Windows interactive backend
validation until the owner runs the included verification.
