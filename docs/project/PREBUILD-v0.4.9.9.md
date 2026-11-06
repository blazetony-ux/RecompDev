# v0.4.9.9 — native functional migration scope and build record

**Owner direction:** On 2026-11-06 the owner instructed: "just port the old stuff to the new infrastructure and build it". This is direct authorisation to implement the existing-capability migration, **not** an assertion that all historical functions have already been ported. The full formal approval workflow described in the [development contract](DEVELOPMENT-CONTRACT.md) was not separately followed with an advance owner-approved pre-build report. That deviation is disclosed here, not disguised as prior approval.

**Baseline:** Owner-installed `workspace/v0.4.9.8`, commit `f227ef688d1cf05d2d5b4597777b25f0c0b7d592`; v0.4.9.7 never installed. The previous permanent root installer remains unchanged. All 581 + 61 original-source historical files remain untouched. Source/data/output roots remain separate.

## Native implementation and ABI

- `RecompDev.exe` 0.4.5 -> **0.4.6**: `--stage native-execute --rom <file> --game rd_<name> --out <prefix> [--steps N]` runs authenticated P-code-generated DLL instructions in the compiled controller, using the previously validated C++ harness runner code linked into both EXEs. Default *native-only* mode refuses missing compiled instructions; `--allow-fallback` is explicit and still limited by the original fixture CPU interpreter. Requires exact ROM SHA-256 and byte-size exported by the supplied game DLL, independently of per-instruction source guards. Loader's module-kind/API checks remain active. The compiled controller does not launch Python for this stage.
- `rd_cpu_z80.dll` 0.3.0 -> **0.4.0**: source-only decode for base/CB/documented ED/DD/FD indexed forms; reuses frozen `nativepilot/z80_cycles.hpp` ED timing qualification. Abstract register-A/SP and source-write facts are exported through versioned extensions, not implemented in the controller. This is **not** a fully ported Z80 interpreter or proof of instruction semantic parity.
- `rd_machine_sms.dll` 0.2.0 -> **0.3.0**: initial `{{0,0,1,2}}` mapping and mapper-write context imported from the original `rd::State`; unresolved mappings fail closed and unknown writes invalidate context. Native discovery no longer presumes every PC is from the initial 1 KiB. It does not modify the existing machine runtime bus ABI.
- `rd_native_game_runner` is shared C++ build code reused by `RecompDevHarness.exe` and the production controller, **not** a new deployed DLL or separate orchestrator. No new Python/PowerShell release wrapper is added. No title-specific addresses, ROM hashes or logic are embedded in production.

## Real gaps and mandatory acceptance

- Previous historical **P-code generation and auto-recovery are still implemented by preserved Python/Ghidra code**; this build migrates **compiled game-DLL execution**, not the full generator. Existing `prepare`/`recover` remain transitional and unmodified. Full port of the generator, IA/IY/shadow register and interrupt semantics, native full-game execution, 68000/MIPS CPU translators, and deterministic Shinobi gameplay parity remain open.
- Synthetic test: compiled `RecompDev.exe` must execute 3 source-attested instructions from the original synthetic P-code DLL with 0 fallback, and reject a modified ROM plus unsafe plugin names.
- Mapper test: generic startup sequence including `ED 56`, `LD (0xFFFF),A` with A=6, and `CALL 0x8A68` must resolve physical `0x18A68`, then block that resolution if A is unknown. No copyrighted commercial ROM bytes are shipped. The real owner's Shinobi discovery should be retested on Windows before claiming real-ROM improvement.
- Existing native CTest, docs, Python, release-protocol and 642-file integrity gates must pass; Windows MSVC build/CTests and DLL activation are owner-side acceptance and remain UNVERIFIED in the package developer's Linux environment. Windows gameplay or translation parity are NOT established.
- Rollback uses unchanged `Install-RecompDev-Release.ps1` in the committed v0.4.9.8 checkout: SHA-pinned ZIP, exact Git baseline, staged external tests, commit/tag/bundle/active-binary verification. No manual ZIP copying.

## Exclusions and Shinobi continuity

No changes to Shinobi-generated projects, live monitor, deterministic input capture, sprite/video pipeline, or protected original code. The historical stop `0x4F9E` and scrolling anomaly remain unresolved. No claim of playable game or completed ROM->P-code->compiled native game through the new DLL controller.
