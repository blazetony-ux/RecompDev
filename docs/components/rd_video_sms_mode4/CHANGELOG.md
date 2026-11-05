# rd_video_sms_mode4 — independent component history

## [0.1.0] - 2026-11-05

- **Changed:** Introduced A standalone C ABI DLL for the Sega Master System Mode 4 framebuffer. Accepts VRAM, CRAM and VDP registers from the machine adapter, produces BGRA pixels and optional sprite diagnostics. Hardware-specific behaviour is isolated from the CPU and generic window host.
- **Validation:** Standalone C++ sprite/priority/overflow regression, external staged generated-game compilation and ABI execution, SHA-verified staging and existing historical preservation tests. Windows deployment and real Shinobi sprite appearance still require the user's next run.
- **Compatibility:** ABI version 0x00010000 is separate from the generic runtime host. Existing controller v0.4.4, Z80 DLL v0.2.0, runtime host DLL v0.1.0 and frozen v0.4.0.45 translator retain their published versions. Does not implement VDP status-bit/scanline timing parity or translate additional game instructions.
