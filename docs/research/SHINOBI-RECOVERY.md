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

## 2026-11-05 — v0.4.9.5 owner runtime and v0.4.9.6 carry-forward

**Install / monitor:** The owner verified 44/44 Windows CTests in v0.4.9.5 commit `cceb081ae1f4bb9d9b04060ae5868d087a69dead`, then demonstrated that the independent controller-mediated Live Execution Monitor captures and retains guest Z80 instruction/input/stop events. This is a monitor acceptance result only, not gameplay or hardware parity.

**Deterministic replay:** A captured Z-button input run stopped at frame 196 at `0x7BE8` (`UNTRANSLATED_INITIAL_CODE`). Recovery preflight reproduced that frame and stop address exactly. Preserved source-verified recovery subsequently completed an 1,800-frame budget in recovery round 02, but the displayed stage was unchanged from about frame 575 onward and independent hardware parity was not tested. These are existing recovery capabilities, not a new game-specific translation patch.

**Interactive movement:** A subsequent Right-key session produced guest input port `0xDC=0xF7` with zero input mismatches. The owner observed incorrect/reversed screen scrolling, then untranslated code at `0x4F9E` and termination around frame 730. The code stop is a separate translation coverage issue; neither an R8 wraparound nor the player's visual impression identifies the responsible component without independent reference alignment. Historical `0x56C7`, `0x7BE8`, `0xB2E1` and earlier stopping conditions remain recorded, not new discoveries.

**Protected next gate:** Maintain and extend generic CPU/translation/memory/VDP/input/interrupt correctness evidence and deterministic cross-game reference comparisons. Do not add Shinobi ROM hashes, addresses or function-specific execution paths to production source. v0.4.9.6 updates only universal discovery metadata/providers and release governance, leaving the native game, recovery cache, Z80 DLL, SMS video DLL and execution monitor unchanged.
