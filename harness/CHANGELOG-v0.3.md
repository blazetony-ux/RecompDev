# v0.3 release notes

- Added dedicated `rd_game_probe` development plugin for real-ROM exploration, with explicit `--probe` opt-in. Never passes probe mode off as native recompilation.
- Added JSON reports for blocked opcodes in exploratory mode, with zero-cycle `EXECUTION_BLOCKED` events and source SHA-256 in reports.
- Added isolated `rd_game_owner` target and `Run-RealRom-Windows.ps1` code generation / MSVC build / execution / discovery-sidecar workflow.
- Hardened strict real-ROM P-code input with explicit declared Ghidra producer label, byte matching, bank mapping, source fingerprint checks; original synthetic generated regression module retained.
- Added `import_runtime_observations.py` for genuine external file paths and strict validation into a **new** RecompDev v0.4.0.45 schema sidecar. Source bytes and source identity are verified before any SQLite database is created. No bytes of external ROM are shipped.
- Added end-to-end tests for probe incomplete-stop, no-native coverage, source-attested runtime events, sidecar provenance, event tampering, stale input and overwrite rejection.
- Original 18 tests remain unchanged in semantics. At release, 19/19 passed on Linux; Windows validation is pending.

Not done: comprehensive Z80 interpreter, full gameplay, autonomous Ghidra extraction, independent MAME parity, ROM-free executable. The master RecompDev v0.4.0.45 roadmap and files remain unchanged.
