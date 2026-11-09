# rd_video_sms_mode4

Scope: `production-video`; registered and independently versioned in `workspace/components.json`.

A standalone C ABI DLL for the Sega Master System Mode 4 framebuffer. Accepts VRAM, CRAM and VDP registers from the machine adapter, produces BGRA pixels and optional sprite diagnostics. Hardware-specific behaviour is isolated from the CPU and generic window host.

The v0.1.1 source correction implements R8 horizontal scroll direction and fixed-screen R0 zones plus backdrop/left-mask semantics. The exported `rd_sms_mode4_render` ABI is unchanged. Because the caller supplies only one 16-byte register snapshot per frame, mid-frame scroll register writes and raster line latching are still **unmodelled**; ROM screenshot parity cannot be inferred from the new register-focused pixel tests.

The new video component does not claim pixel-level Master System hardware parity. It operates only on display output and the accompanying diagnostics; guest VDP status-bit timing remains to be qualified. Changing this plugin must not require recompiling the controller, CPU decoder, generic host DLL or the preserved translator.
