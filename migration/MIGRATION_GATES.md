# RecompDev v0.4.0.45 -> Modular Harness: zero-loss migration gates

**Baseline status: inventoried, NOT migrated or independently validated.**

## Immutable baselines

- v0.4.0.45 original source archive: `RecompDev-0445.zip` (**581 files**, including `catalogue.sqlite`).
- Modular harness v0.3 source archive: `RecompDev-ModularHarness-PoC-v0.3-Source.zip` (**61 files**).
- Use `source-integrity-manifest.json` and `verify_baseline.py` to verify every member and both ZIPs before modifying or extracting any working copies.
- No files or SQLite databases in either original archive have been modified as part of this audit.

## Non-negotiable rules

1. **Preservation before porting.** Archive every v0.4.0.45 file unchanged, including older tools, baselines, regressions, reports, manifest and generated evidence. Preserve v0.3 source as a separate baseline.
2. **Capability-by-capability migration registry.** Every component/evidence format gets an owner, source path, new interface, implementation status, tests, blockers and a rollback reference. Nothing marked 'done' solely because it loads as a DLL.
3. **Adapters first.** Keep working original code behind DLL/service interfaces. Refactor only with differential tests. Allow build-time Python, Ghidra or tooling components to remain external services; DLLs are not the correct boundary for every component.
4. **No evidence downgrades.** Preserve SHA256 identities, observed/source-derived/verified qualification levels, complete bank identity, ordered hardware events, rollback eligibility, and immutable reports. Unknown and unqualified must never silently become translated or native-qualified.
5. **Database safety.** Preserve existing database bytes as immutable backups. Migrations operate on copies, carry forward all records, verify table counts/keys/provenance and detect schema drift. Do not overwrite production catalogue or owner-local evidence.
6. **Comparative regression gates.** Old verification commands must keep passing, as must new plugin tests, direct reference parity, multi-game SMS regression, and existing M68000/MIPS fixtures. Benchmark behavior as well as functionality. Fail closed on missing capability.
7. **No source ROM dependency in final native releases.** Discovery and validation builds may use owner-local originals; release build cannot hide ROM bytes in an EXE/resource pack. Unknown dependencies must block qualification.
8. **No cutover before equivalence.** Keep v0.4.0.45 operational as baseline, migrate in parallel, cut over each capability only when parity is established. Roll back independently if any old regression fails.

## Preservation / interface map

| v0.4.0.45 source | New architecture owner | Required validation before claiming migrated |
|---|---|---|
| `nativepilot`, `nativecore`, `multisa`, `native_batch.py` | Translation/generator build-time services + generated game module | Exact source-attested instruction lowering, flags, cycles, banked dispatch, native-commit verification, M68000/MIPS holdouts |
| `hardware`, `systems/mastersystem`, `adapters`, `host` | Machine device plugins + presentation/audio/input backends | CPU-neutral device contract; VDP/CRAM/PSG/input and scanline/IRQ regression; no duplicate authoritative state |
| `discovery`, `recovery`, `campaign`, `tooling` | Discovery/analysis services, cataloguing and repair plugin adapters | Semantic equivalence of recorded evidence, qualified states, retry/rollback, session reproducibility |
| `ghidra`, `bridge`, `tools`, `static` | Optional analysis/export tools and operator frontend | Function-export provenance and byte identity; export formats and UI workflows preserved |
| `catalogue.sqlite`, `baselines`, `evidence`, `BUILD_*`, `FILE_SHA256_*` | Immutable evidence store and migration/import tooling | No lost rows, identifiers, provenance, or stored reports; backed-up before any schema changes |
| `systems/megadrive`, `systems/psx`, M68000/MIPS infrastructure | Machine profiles and ISA plugin registrations (do not claim full consoles) | Existing preparation/blocker behaviours and restricted backend regressions remain intact |
| `tests`, `Verify-*.ps1`, release/handovers/charter | Cross-release regression suite and immutable project governance | All original applicable checks run, limitations preserved, new tests added not substituted |

## External owner-local evidence — NOT in uploaded v0.4.0.45 ZIP

The v0.4.0.45 release notes reference `RecompDev-Data/catalogue.sqlite` and `RecompDev-Data/verified-coverage-v0443.sqlite`; neither is in the uploaded archive. Other owner-local Ghidra project databases, custom analysis logs, intermediate evidence and catalogue changes after archive creation may also exist. **A zero-loss claim covering all historical learning cannot be made without an inventory and separately backed-up copy of those external sources.** Do not delete or move them as a prerequisite; inventory their paths, sizes, hashes and schemas, then import from read-only copies.

## Ordered integration gates

- **G0 Freeze:** establish exact SHA256 baselines for v0.4.0.45 and harness v0.3 and inventory extra local evidence.
- **G1 Map:** machine-readable module/evidence registry covering every source component and every regression suite.
- **G2 Bridge:** wrap the existing CPU-neutral hardware/machine and translation/discovery implementations, retaining original semantics and data types.
- **G3 Execute:** generated modules and fallback share one CPU/bus/scheduler state; demonstrate real Z80 and holdout, bank and IRQ behaviour without game-specific code.
- **G4 Discover:** authenticated exports, complete evidence provenance, safe separate SQLite sidecar and no false qualification.
- **G5 Prove:** run legacy v0.4.0.45 validation and new cross-architecture, multi-game and independent reference checks.
- **G6 Release:** no dependency on source ROM at runtime, asset closure, rollback proven, and only then promote the new architecture.

**Scope note:** These are acceptance gates for a future migration, not completed implementation. An unchanged source archive alone is evidence of file preservation, not behavioural parity. Historical project facts outside the uploaded archive cannot be reconstructed from a new harness.
