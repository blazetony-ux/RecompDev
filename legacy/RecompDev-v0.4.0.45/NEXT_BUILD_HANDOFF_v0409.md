# RecompDev v0.4.0.9 engineering handoff

Keep **game-independent** development as a release gate. Shinobi is a regression test, not a special target.

## Added

- `nativecore/instruction_evidence.py`: byte-confidence screen at an authenticated physical ROM entry; protects padding from blind native dispatch.
- `ghidra/ExportExactInstruction.java`: direct, at most 64 instruction P-code export at seeded logical PC independent of Function construction.
- `nativepilot/recovery.py`: both Ghidra exports, exact-entry provenance/attestation and refusal artifacts.
- `nativecore/parity.py`: explicit reference checkpoint comparison; does not fabricate reference traces.
- `tests/test_exact_instruction_recovery_v0409.py`: exact export, hash forgery, FF filler and checkpoint mismatch tests.
- Workbench execution timeline can show exact recovery classification and reasons.

## Next engineering milestones

1. Run the exact exporter on actual Ghidra 12.2 and inspect `entry-diagnostics.json` for source-attested fixed vectors. Prove whether FF padding or disassembler function omission explains the stop; do not override suspicious padding by game name.
2. Capture independent CPU/VBlank references via a legally usable emulator trace adapter and align checkpoints by event or instruction. Reject mismatched IFF, program counters and hardware effects.
3. Generalise Z80 initial-ROM, vector and indirect-branch function boundaries and improve Ghidra RAM mapping without sacrificing provenance.
4. Remove legacy hardcoded `0xC001` telemetry in favour of generic watchpoints with compatibility migration.
5. Broaden to a second actual Master System title and start executing verified 68000 snippets via the same backend contract.

## Provenance guardrails

Original ROMs are owner-local. Any byte-hash mismatch or unverified code boundary must stop compilation. Exporting one instruction is *not* proof it is executable code. Reference parity remains `NOT_TESTED` until independent evidence is actually supplied.
