# v0.4.0.35 handoff — integrate an actual second Z80 machine

1. Refactor nativepilot State into core Z80 state and injected machine-specific bus contract, keeping the existing SMS code path byte-for-byte testable.
2. Select a small open test machine/format (e.g. ZX Spectrum 48K bare test payload) with independently asserted load/entry/port map; never treat .z80 snapshots as flat ROM.
3. Build real memory/IO/frame/IRQ adapter, and compare selected instruction + IO event traces with an independent reference.
4. Test generated x86-64 binary, no CPU-interpreter fallback. Keep Shinobi and legacy M68K/MIPS tests as non-regression gates.
5. Expand evidence to signed/validated platform manifests and reject mismatched platform/core claims at each execution entrypoint.
