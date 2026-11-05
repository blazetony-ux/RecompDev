# sms_video_integration

Scope: `production-video-integration`; registered and independently versioned in `workspace/components.json`.

Source staging and dynamic DLL selection for generated native games; patches only the copied VDP renderer in the external runtime cache and records provenance. The original historical renderer, Z80 translation and ROM remain immutable.

The new video component does not claim pixel-level Master System hardware parity. It operates only on display output and the accompanying diagnostics; guest VDP status-bit timing remains to be qualified. Changing this plugin must not require recompiling the controller, CPU decoder, generic host DLL or the preserved translator.
