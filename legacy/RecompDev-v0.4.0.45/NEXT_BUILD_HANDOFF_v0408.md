# RecompDev v0.4.0.8 engineering handoff

**Strategic rule:** Game-specific execution failures must yield reusable system/CPU tools. Do not implement another fixed Shinobi code path.

## Current reusable contracts

- `nativecore/registry.py`: capability declarations; Z80/SMS experimental native C++ output, m68k/Mega Drive and MIPS/PS-X EXE preparation only.
- `nativecore/adapters.py`: region mapping and source-attested recovery provider.
- `nativecore/recovery.py`: shared bounded planner that handles both untranslated initial code and cartridge banks.
- `nativepilot/engine.py`: source-verified C++ → build → replay orchestration and persistent evidence; hardware side in `systems/mastersystem`.
- `nativeprep/engine.py`: common catalogue target registration and source verification. MIPS target registration no longer blocked by the SMS-only whitelist.
- `static/execution.*`: system-capability matrix and configurable RAM watchpoints.

## Next tasks (priority order)

1. Evaluate **real Windows Shinobi** run at `0x0038`: inspect actual Ghidra seeding results; if the vector is a jump or overlap, extend the generic interrupt/entrypoint disassembly strategy without hard-coded addresses.
2. Build actual M68K and MIPS backends behind the same ISA lowering interface, starting with instruction forms verified by independent compiler and CPU traces. Do not conflate existing graph recovery with native execution.
3. Add independent reference execution and differential CPU/hardware trace comparison, per system.
4. Move legacy `0xC001` counters into generic watchpoint diagnostics after existing tests/evidence migration is complete.
5. Extend hardware plugin contracts and support a **second actual commercial/owner-authorized or homebrew SMS game** without game-name logic.
6. Add native project exporter independent of a fixed SMS binary harness and replace approximate tick timing with verified instruction cycle behavior.

## Genuine acceptance evidence

Two different synthetic SMS images recover a fixed `0x0038` vector using the same flow. Banked-code auto-recovery remains backwards compatible. MD and PS-X EXE preparation can register targets but reject false native execution claims. ROM hashes are checked before C++ generation and before executing the compiled binary.

The first real Windows test remains outstanding, and real playable game output is **not verified**.
