# RecompDev Modular Migration v0.4.2

This release adds a compiled direct-entry native controller, bounded recovery continuation, detailed native-step and frame reporting, and observational hardware diagnostics. The controller still uses **unchanged** v0.4.0.45 discovery, Ghidra preparation, verification and C++ native-recovery implementations via Python service adapters. This is intentional and is not a full native rewrite.

# RecompDev Modular Migration v0.4.1 — Earlier capability restoration (parallel branch)

**The v0.4.0.45 source remains the authoritative implementation.** The modular harness remains separate. This release provides a genuinely executable, plugin-routed front end to the original discovery, Ghidra/native-preparation and compiled continuous-recovery services. It is NOT a replacement or rewrite of their internals.

## What is newly runnable

- `modular/cli.py run-rom` reads a genuine owner ROM without copying it, opens a **new catalogue cloned via SQLite online backup**, invokes actual `discovery.engine`, then optionally `nativeprep.engine`, then optionally `tools/Run-Continuous-Recovery-v0445.py` (using the original C++ build path). Every stage has independent logs and explicitly reports success, blocked states and source identities.
- `modular/cli.py compare-discovery` runs the original v0.4.0.45 discovery CLI and the modular plugin route against identical catalogue snapshots and the same source input; compares stable source/region/task/asset/file rows, ignoring transient timestamps and output paths. This proves transparent routing for the tested discovery workload, not independent Z80 or hardware parity.
- Three modular service plugins are registered through `modular/plugins.json` and checked against their **unchanged production module paths**, not a mock engine.
- Both preserved archives and their complete extracted file inventories remain hash checked (581 + 61 files). Selected legacy tests and previous harness DLL tests remain part of the release.
- For authenticated P-code exports, the actual legacy C++ continuous recovery engine is invoked and produces source-bound native project and execution reports, with observed blockers rather than synthetic success.

## Owner acceptance (Windows, one-line commands)

Install the self-contained `Install-RecompDev-ModularMigration-v0.4.1.ps1` script. Default location: `C:\Projects\RecompDev-ModularMigration-v0.4.1`. No manual extraction.

Run real ROM discovery and Ghidra preparation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\RecompDev-ModularMigration-v0.4.1\Run-Modular-ROM-Windows.ps1" -Rom "C:\Roms\MASTERSYSTEM\Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms" -Stage prepare
```

Run old-vs-modular discovery comparison on a real ROM:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\RecompDev-ModularMigration-v0.4.1\Compare-Legacy-Modular-Windows.ps1" -Rom "C:\Roms\MASTERSYSTEM\Bank Panic (Europe).sms" -Budget 150
```

For an authenticated Ghidra export, use `-Stage recover -Export "C:\Exports\functions.json"` (and optionally `-Steps 200000 -Frames 120 -MaxRecoveries 2 -CaptureHardware`). The export must match the exact ROM and every instruction byte; any missing bank or unsupported native path is a blocker, never game-play parity.

For a specific owner catalogue, pass `-Catalogue "C:\Projects\RecompDev-Data\catalogue.sqlite"`. **The source database is opened read-only and backed up into a new per-run working database. No production database is modified or replaced.** Owner-local catalogues were not present in the uploaded release, and are therefore not migrated automatically.

All run reports live in `evidence/modular-v041/<UTC-run-id>/`, with `controller-report.json`, `working-catalogue.sqlite`, a `discovery-report.json`, optional `preparation-report.json`, optional recovery output, and individual stage logs. Failed/blocked runs are still retained as evidence. The CLI exits nonzero for blocked states; this is deliberate.

## Existing preserved work

- Original discovery and function-recovery orchestration, Ghidra integration, Z80 P-code lowering, native C++ projects, verified coverage/campaign tools, memory/bus/timing, Master System VDP/PSG/input, original M68000/MIPS analysis, MD/PSX preparatory plugins and tests are **included byte-for-byte**. Except for the three adapters above, these capabilities remain available through their unchanged legacy entry points; most have **not been individually converted into DLLs**.
- `harness/RecompDevHarness.exe` and its independent CPU, machine, audio, video, input, discovery and translated-code DLLs still build and pass their tests. Its *limited* Z80 interpreter remains a distinct experimental tool: it does not substitute for the original native recovery pipeline.

## Qualification limits / remaining cutover gates

1. Discovery adapter output equivalence: demonstrated on the bundled synthetic SMS test ROM. **Real owner-ROM equivalence is a required subsequent Windows gate.**
2. Original Ghidra native preparation: invoked through the adapter and reports missing tool as a blocker. No actual Ghidra export was supplied with the archive; real-game Ghidra recovery not verified in this environment.
3. Original C++ continuous recovery: invoked, source-attests synthetic P-code and compiles/runs native code; still hits an untranslated banked path on the test. No claim of completed game translation.
4. Full original suite (`Verify-v0445.ps1 -Full`) and owner-local historical evidence inventory remain required; original sources and packaged catalogue are preserved, **external owner files are not in the package**.
5. No real-game gameplay, full CPU state parity, interactive Windows playback, ROM-free asset closure or complete transition to independently swappable DLLs is established.

**No cutover is authorised.** The original v0.4.0.45 remains primary until real-game equivalence and missing capabilities are independently verified.

### Restored seven-game campaign

`Run-SMS-Campaign-Windows.ps1` launches the unchanged `tools/Run-SMS-Campaign-v0445.py` inside an isolated *disposable copy* of the original release, using the new working-catalogue path via `RECOMPDEV_CATALOGUE`. It recognises the existing v0.4.0.45 seven-game list (Shinobi, Bank Panic, Alex Kidd, Fantasy Zone, R-Type, Sonic SMS, Wonder Boy). Individual failures are preserved in the original campaign summary; a complete driver invocation is **not** proof of gameplay parity.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\RecompDev-ModularMigration-v0.4.1\Run-SMS-Campaign-Windows.ps1" -RomDir "C:\Roms\MASTERSYSTEM" -Frames 120 -Steps 200000
```

By default the controller *prefers* `C:\Projects\RecompDev-Data\catalogue.sqlite` if that owner-local file exists. It is always read-only/snapshotted to the per-run working DB; if absent, the release uses its immutable bundled seed. Use `-Catalogue` to choose any other source explicitly. No automatic import or mutation occurs in the external database.

### Validation accounting

Default release gate: **30 CTest groups on Linux**, including source preservation, plugin registration, original-versus-modular discovery canonical row parity, genuine native-preparation blocking, ; the unchanged seven-game campaign orchestration was separately tested against an empty ROM folder, correctly returning `NO_MATCHING_ROMS`.

The campaign subprocess test is available separately with `py -3 modular/tests/test_integration.py TestRealLegacyServices.test_original_seven_game_campaign_dispatch -v`. It passed independently but is not part of the default CTest build following intermittent long-running combined-suite stalls.

The native compilation-and-execution *extended* gate is available separately via `Run-Extended-Recovery-Windows.ps1`. It passed as a standalone Linux test on a source-attested synthetic Ghidra-format export and observed `BANKED_CODE_NOT_TRANSLATED` after compiling a native project. It is intentionally outside the default CTest suite after intermittent long-running process stalls in a combined CI run. That limitation is not silently counted as a default release pass.
