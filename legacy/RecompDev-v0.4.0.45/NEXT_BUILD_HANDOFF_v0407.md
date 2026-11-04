# RecompDev v0.4.0.7 engineering handoff

Previous owner v0.4.0.6 Shinobi: 500,000 compiled steps, ~1,856 VRAM and 32 CRAM writes, 22 PSG writes, 3 bank switches. Black 256x192 diagnostic PNG. PCs at 0x0BEF..0x0BF4 polling 0xC001, likely awaiting a hardware-driven flag but not proven without reference execution. The compiler, bank mapping and prior bank-6 recovery are working.

v0.4.0.7: experimental approximate NTSC VBlank/IM0/IM1 IRQ scheduler integrated with native generated C++ and ROM-attested bank dispatch; Z80 EI latency, HALT idle ticks, interrupt stack entry, IM2 stop and NMI helper. Native frame/CPU/VDP/C001 diagnostics plus local hardware-state dumps. Synthetic generated C++ proves VBlank IRQ can release a RAM-flag wait. No exact timing, Shinobi parity or verified graphics claimed.

Next: run Shinobi; determine whether C001 changes and whether any VBlank IRQ reaches a source-attested handler. If not, capture exact native execution around EI/VDP register1/IRQ handler and compare against an independent reference trace before modifying timing or treating event delivery as correct. Fix authentic graphics only after confirmed register/VRAM/CRAM state. Address IRQ line/scroll/sprite timing and complete CPU op parity. Preserve reusable portable hardware runtime and universal Z80 backend.
