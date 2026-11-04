# Shinobi real-ROM recovery observations

**Status:** Owner-reported v0.4.2/v0.4.3 run evidence. These are observations, not independently validated emulation or gameplay correctness.

## Native recovery

The source SHA-256 recorded for `Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms` is `dac4f1dcb41193cb42a96950444a87c5f2952ea66474c59a38c07b10ac411e47`. Ghidra preparation reported 48 candidate functions and 2,114 physically authenticated instructions across 3,912 source bytes. The compiled controller permitted three recovery rounds with `--steps 1000000 --frames 120 --max-recoveries 2 --max-rounds 3`. Final status `CONTINUOUS_SESSION_COMPLETE`, stop reason `FRAME_BUDGET_REACHED`, maximum native steps 709,841, recovered instruction addresses 3,372.

## Hardware observations

The final round reported 120 VBlank events, 34 accepted maskable interrupts, 32,942 VDP writes, 128 CRAM writes, 11 PSG writes, 24 distinct frame hashes and zero nonzero captured audio samples. v0.4.3 offline reviewer analysed 120 per-frame timing rows; eight attempt sessions had display observations, seven WAV captures were genuinely silent, and the final captured 256×192 image contained 3,702 nonblack pixels in two colours. Original raw VRAM and CRAM buffers were not present in those sessions.

## Interpretations not supported

A frame budget does **not** show a playable ROM-independent game. Distinct framebuffer hashes do not mean independent saved frame images. PSG writes with silent PCM do not uniquely identify the sound fault. Source-byte attestation does not prove translated instruction semantics, cycle or interrupt parity. Independent emulator or real hardware comparisons with aligned timing/inputs remain missing.

## What to capture next

Source-captured VRAM (16 KiB), CRAM (32 bytes), VDP registers, sprite state and timestamped PSG register writes at configured frame checkpoints; reference test input/region and per-frame CPU/IRQ timing. See [hardware validation gaps](HARDWARE-VALIDATION-GAPS.md).
