# sms_video_integration — independent component history

## [0.1.0] - 2026-11-05

- **Changed:** Introduced Source staging and dynamic DLL selection for generated native games; patches only the copied VDP renderer in the external runtime cache and records provenance. The original historical renderer, Z80 translation and ROM remain immutable.
- **Validation:** Standalone C++ sprite/priority/overflow regression, external staged generated-game compilation and ABI execution, SHA-verified staging and existing historical preservation tests. Windows deployment and real Shinobi sprite appearance still require the user's next run.
- **Compatibility:** ABI version 0x00010000 is separate from the generic runtime host. Existing controller v0.4.4, Z80 DLL v0.2.0, runtime host DLL v0.1.0 and frozen v0.4.0.45 translator retain their published versions. Does not implement VDP status-bit/scanline timing parity or translate additional game instructions.
