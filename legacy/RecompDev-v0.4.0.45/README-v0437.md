# RecompDev v0.4.0.37 — Proof-first native output / MAME evidence gates

**Strategic direction:** correctness before coverage. The Z80/SMS native pipeline, bounded recovery, seven-game campaign, and earlier evidence are preserved. v0437 does **not** claim playable Shinobi, instruction-level MAME parity or fully correct SMS hardware.

## New compiled device qualification

- `hardware/tests/output_probe_v0437/main.cpp`: builds actual shared SMS Mode 4 renderer, PSG synth, shared PPM serializer and PCM WAV writer as native C++.
- `nativecore/output_qualification_v0437.py`: computes expected RGB and PCM independently of compiled C++ and checks the *entire files* byte for byte, with tamper-negative tests. Expected 256×192 half red/half blue output, 4410 nonzero audio samples.
- `tools/Validate-Native-Outputs-v0437.py`: compiles/runs test and emits immutable-hash report. The native app and generated native projects also use `hardware/image_io.hpp` for PPM writing.
- This establishes **controlled backend output function**, not guest ROM correctness, MAME PSG accuracy or VDP timing equivalence. The renderer and PSG retain their earlier approximation limitations. **It does not make a black/silent game playable.**

## Independent reference (owner-local, optional)

- `tools/Run-Shinobi-Reference-v0437.py` reuses the *existing* v0436 native Shinobi session and attempts a fresh 120-frame MAME run of the **same original ROM hash** through the v0436 independent MAME-frame observer. MAME is not bundled and must be supplied by the owner. No new native recompilation is required.
- `nativecore/reference_parity_v0437.py` rejects wrong-ROM, tampered reference, missing original capture, incomplete frames and invalid producer/executable identities. It records the first differing sampled PC/SP at matching **frame ordinal** but classifies even identical samples as **unaligned**. Matching ordinal samples are not proof of identical frame phase, initial CPU state or Z80 instruction boundaries.
- `tools/Compare-MAME-Native-v0437.py` can compare an already-captured MAME reference directory against an existing native session.
- The MAME reference exporter remains `tools/Capture-MAME-SMS.py`; full CPU-step alignment, reference framebuffer comparison and automatic verified repair remain **open milestones**, not implemented features.

## Installation — Windows PowerShell (three commands, one line each)

Close the existing Workbench first.

1. Extract:

`Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.37-Parity-Foundation.zip" -DestinationPath 'C:\Projects' -Force`

2. Full verification:

`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.37\Verify-v0437.ps1'`

3. Launch Workbench:

`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.37\Run-Workbench.ps1'`

## Targeted evidence for next engineering decision

Compiled expected-pixel and expected-PCM verification is part of step 2. Report its pass/fail rather than running another seven-game campaign immediately.

**If MAME is installed and available on PATH**, open a separate PowerShell and run:

`py -3 'C:\Projects\RecompDev-v0.4.0.37\tools\Run-Shinobi-Reference-v0437.py'`

If MAME is installed elsewhere, add `--mame 'C:\path\to\mame.exe'` to the same command. The tool locates the most recent v0436 Shinobi session under `C:\Projects\RecompDev-v0.4.0.36\evidence`, verifies source ROM hashes and outputs `EVIDENCE_ZIP=...`. It will fail closed with a useful message if a matching session, BIOS or MAME installation is unavailable. The MAME script may need adaptation to an installed MAME version's Lua API; failure remains evidence of a reference-integration blocker, not a guest CPU divergence.

**Acceptance boundaries:** 1) compiled device output exact fixture match, 2) mandatory compiled/recovery/bridge regressions, 3) independent ROM-identified MAME observation capability when available. Genuine reset/step-aligned Shinobi parity and a correct end-to-end native game remain the next milestones.

No original ROMs, game-specific patches, binary game output, or MAME files are distributed.
