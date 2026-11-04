# v0.4.0.31 handoff

- Source-authenticated Workbench history must never accept a non-64-hex source ID; legacy discovery records are listed as diagnostics.
- Always merge graph target SHA-256 identities with valid discovery IDs before looking up real native campaign history.
- Owner Windows API request is pending. Reuse Shinobi job `29edb84c1c785cea`; no ROM rerun is needed for history testing.
- Sonic real M68000 discovery increased to 1,777 instructions / 77 static function candidates, 6 barriers, 39 recovered edges (source-supported, independently unverified); Ridge Racer MIPS remains 14,222 / 213 with 81 barriers.
- Next substantive work: extend MIPS target inference and verify authenticity via independent reference checkpoints; do not claim playable games or native non-Z80 compilation.
