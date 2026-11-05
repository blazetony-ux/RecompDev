# movement_trace — native movement correctness instrumentation

Scope: `production-diagnostics`; registered as an independently versioned source-only tooling component in `workspace/components.json`. Version 0.2.0.

This component stages observation-only probes in disposable, source-attested native game projects. Its platform- and CPU-neutral recorder accepts the current guest cycle, logical host controller state, actual guest I/O-port readbacks, display scroll registers, and raw sprite-attribute-table entries. The Master System adapter identifies ports 0xDC/0xDD and VDP R8/R9, but **neither the controller nor the generic runtime-host DLL contains that console-specific logic**.

All diagnostic files are opt-in via `Run-Native-Game.ps1 -MovementTrace`. The launcher places `movement-controller.csv`, `movement-port-reads.csv`, `movement-frames.csv`, `movement-sprites.csv` and `movement-diagnostics.json` in the standard automatic evidence ZIP. `guest-input-cycles.csv` remains the existing replay input source; no controller mapping changes. Historical `legacy/`, generated `translated.cpp`, original ROMs, existing DLLs and Workbench are unchanged.

The diagnostic checks active-low controller-bit mapping and recorded actual guest reads; it does **not** infer Shinobi's player identity, world coordinates, keyboard intent or hardware parity from arbitrary sprite positions. Sprite positions and VDP scroll register values are observable evidence only. When no guest input ports are read, the report explicitly says `INSUFFICIENT_CONTROLLER_READS`.

See `docs/releases/v0.4.9.3.md` for Windows validation instructions and known limitations. The existing native-code stop at 0x1E09 remains an independent execution-coverage issue.

## v0.2.0 — generic guest state observation integration

`movement_trace` now instantiates `state_observer` 0.1.0 through an SMS-only staged adapter. The actual recorder and offline analysis are hardware-agnostic. The physical SMS RAM region `system_wram` is exposed with address-space metadata and clock domain, rather than scattering direct `state_.ram` knowledge through the generic recorder. This does **not** identify a player position or prove correct gameplay. Per-frame sampling observes boundaries, not every individual store.

The replay remains deterministic: observation occurs in staged copies, changes no translated instruction, and generates `state-memory-regions.csv`, `state-memory-deltas.csv`, `state-memory-summary.csv`, `state-memory-diagnostics.json` within the normal evidence bundle. The memory trace is opt-in and bounded; its status explicitly records truncation. New providers can describe additional memory regions and clocks without modifying the generic recorder.
