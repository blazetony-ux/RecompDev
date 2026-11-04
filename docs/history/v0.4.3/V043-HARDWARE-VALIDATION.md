# RecompDev Modular Migration v0.4.3 — hardware review and asset capture

## Source-of-truth rule

All 581 legacy v0.4.0.45 files and 61 prior modular harness baseline files are preserved by SHA-256. Their production pipeline is invoked, not substituted by a reduced CPU interpreter. The compiled RecompDev executable is a controller that still delegates Python/Ghidra services.

## Implemented

- `RecompDev.exe --analyze-evidence RUN_DIRECTORY [--out OUTPUT_DIRECTORY]`: offline processing of existing native capture output, with its own upload-ready ZIP. No original game ROM is needed for post-run analysis.
- `--capture-hardware` on a live `--stage recover` run additionally writes `hardware-review/hardware-review.json`, `HARDWARE-REVIEW.md`, a CSV of per-frame device counters and converted terminal PNG images inside that run's auto-bundled evidence.
- `--reference-image PNG_OR_PPM` opt-in: exact per-pixel RGB comparison, difference PNG, mismatched-pixel count and mean channel difference. The reference must represent an independently captured, input/frame-aligned display; tools cannot verify provenance or temporal alignment.
- `--reference-session JSON` opt-in: direct comparison of per-frame cycle/steps/IRQ/VDP/PSG counters for shared frame numbers; not sufficient to establish timing parity without compatible accounting/reference alignment.
- WAV 8/16/24/32-bit uncompressed PCM analysis: peak, RMS, first nonzero sample and silence. A silent WAV with guest PSG writes is flagged, not misdiagnosed as a synthesizer defect without register trace.
- Machine-decoder plugin `modular/asset_decoders/sms.py`: only when source hardware buffers exist, exports Master System VDP 4bpp 8×8 planar tiles and 2-bit RGB palettes as PNG atlases, with SHA-256 provenance. It never claims complete sprite/audio extraction, ROM-free gameplay or semantic parity.
- Automatic evidence ZIP contains newly generated reports and PNGs, omits ROM files and `native-project` build trees, and includes integrity manifest. Existing run evidence is retained.

## Shinobi example evidence supplied by owner

The earlier 120-frame run contained 8 complete frame captures (terminal attempts), 7 WAV captures, 120 per-frame hardware-counter rows, 11 PSG writes and silent final PCM. No raw VRAM/CRAM buffers were present; faithful source tile/sprite recovery from this run is **not** available. Twenty-four distinct frame hashes are not 24 saved image frames.

## Unsupported/unfinished — MUST NOT be advertised as proven

- Independent MAME or another emulator's ROM-matched/reference-aligned graphics/audio/interrupt comparison was not available in the supplied evidence. Pixel-reference comparison exists but has not been qualified on a real commercial ROM.
- Root cause of silent PSG WAV is unresolved. No PSG register trace was supplied; a general synthesizer patch would be premature.
- Frame snapshots between terminal captures require a separate capture-cadence integration; the legacy runtime supports a `snapshot_every` lower-level option, but v0.4.3 does not yet route it through recovery.
- Complete asset extraction from compressed/ROM data, source-free game executable, full Z80 parity and real multi-ROM hardware validation are outstanding.

## Cross-game verification

The new capture reviewer has deterministic tests with TWO independent synthetic display/audio/timing fixtures, VRAM and CRAM decoders, reference image/diff tests, and direct compiled EXE execution. They are not a substitute for independent comparison on actual Alex Kidd and Bank Panic ROMs.

## Migration status

A hardware-review and extraction adapter was added to the modular orchestration, not to the immutable v0.4.0.45 legacy source. All prior regression tests remain mandatory.
