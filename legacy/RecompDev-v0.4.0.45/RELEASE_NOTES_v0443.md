# RecompDev v0.4.0.43 — Persistent Recovery and Input-Driven Diagnostics

This release is a standalone software package, not a patch to v0.4.0.42.
`RELEASE_VERSION` and the Workbench report **0.4.0.43**. The shared catalogue
at `C:\Projects\RecompDev-Data\catalogue.sqlite` remains unchanged.

## Delivered

1. **Persistent, source-verified coverage**: a new *separate* SQLite store at
   `RecompDev-Data/verified-coverage-v0443.sqlite` is keyed by original ROM
   SHA-256, Ghidra target identity, ISA and content hash. Each overlay is
   re-verified against source ROM bytes and explicit physical bank mapping on
   every import/reuse. Conflicts and tampering fail closed. Versioned software
   releases share recovered code evidence without copying the main catalogue.
2. **Historical reuse**: when the verified-coverage cache is empty for a ROM,
   the owner-side recovery tool can import its existing `bank-functions.json`
   documents from v0.4.0.42 and v0.4.0.40 evidence directories; no user ROM
   or proprietary translated C++ enters the release archive. The original
   recovery files remain unmodified. The `--history-root` option adds other
   owner-local evidence; `--no-history-import` disables automatic seeding.
3. **Input-aware reset/replay**: existing deterministic controller replay is
   retained across recovery attempts, including newly imported code.
   New reports distinguish imported offsets, newly recovered offsets and
   timings for generation, compilation, replay and source recovery.
4. **Master System PSG corrections**: supported data-byte updates to latched
   volume and noise registers; corrected tone half-period (16 CPU cycles per
   internal PSG count); 16-bit periodic/white noise with Master System tap
   pattern 0x0009. These have compiled register and deterministic-sample tests.
   **This does not establish accurate audio for any commercial game or analogue
   audio parity against original Master System hardware.**
5. **Native frame snapshots and offline timeline**: generated native apps can
   take up to 128 PPM snapshots at configurable `--snapshot-every N` cadence
   (1..600). `tools/View-Frame-Timeline-v0443.py` creates a local HTML/PNG
   timeline from those actual snapshots. No emulator framebuffer is substituted.
6. **Signal and recovery observability**: native reports include nonzero PCM
   sample counts and snapshot counts. Recovery reports preserve per-stage times,
   cache reuse, existing frame/state hashes and explicit non-parity caveats.
7. **Release QA**: version-unique package, SHA-256 release manifest, test
   discovery preflight, compiled Z80/NMI, PSG, source-provenance, output and
   generated-frame snapshots. Prior Windows 8 MiB stack policy is retained.

## What is NOT yet complete

* Hardware/CPU equivalence against MAME for every game, correct continuous
  gameplay, or interactive recompile-and-resume inside a running game process.
* Full guest CPU+VDP+PSG snapshot serialization and **verified** process resume:
  this still requires restoration equivalence tests. Existing recovery remains
  deterministic reset/replay, now with less repeated source discovery.
* Automatic proof-guided CPU divergence repair, fully autonomous input-path
  exploration, and a fully integrated Workbench frame debugger.
* Real-game audio quality and game Start-to-play progression.

## One-time R-Type input-recovery acceptance (Windows owner machine)

Use the existing R-Type ROM and Button-1 replay from v0.4.0.42:

`py -3 'C:\Projects\RecompDev-v0.4.0.43\tools\Run-Continuous-Recovery-v0443.py' --rom 'C:\Roms\MASTERSYSTEM\R-Type (USA).sms' --db 'C:\Projects\RecompDev-Data\catalogue.sqlite' --output-dir 'C:\Projects\RecompDev-v0.4.0.43\evidence\rtype-button1-v0443' --frames 420 --steps 12000000 --max-recoveries 12 --capture-hardware --input-events 'C:\Projects\RecompDev-v0.4.0.42\evidence\native-interaction-v0442\r-type\20261103-194930-016508\start-input.csv'`

The recovery tool will import previous matching source-attested overlays on the
first run, including those from the v0.4.0.42 input-recovery experiment. On a
second run, it reuses the central evidence cache directly. To avoid colliding
with an old evidence folder, choose a fresh `--output-dir` for each run.

No earlier ROM, catalogue or evidence directory is modified. Production
v0.4.0.43 authentic-ROM acceptance is owner-side pending; synthetic compiled
fixtures do not qualify gameplay or MAME parity.
