# offline_analysis — interchangeable static whole-input discovery

**Component:** `offline_analysis` (registered in [workspace/components.json](../../../workspace/components.json))

**Scope:** `production-workflow`. Versioned, *static-only* plugin provider chain; the universal engine knows neither cartridge format, CPU instructions nor console memory maps. It never starts a game or downloads analysis tools. Files are source-bound SHA-256 evidence, not executable native code.

## Stable owner interface

```powershell
& $exe analyze --rom 'C:\Roms\example.sms' --out 'C:\Projects\RecompDev-Evidence\offline-v35-example' --budget 40000
& $exe analyze --profiles
```

The same command and report schema apply regardless of image type. `--profile` chooses only a registered profile and **does not force** a wrong format to be decoded. On supported inputs, a successful static-analysis run returns 0; unrecognised inputs return 2 with an explicit `UNSUPPORTED_FORMAT` manifest; invalid/unsafe input or output returns 3. The parent of a fresh output folder is created automatically. The output folder must not exist. Inputs are not modified; symlinks are refused. The process is bounded by 64 MiB per source and 100,000 static instruction candidates, and rejects decoding outside provider-attested source bytes.

## Interchangeable plugin boundary

`profiles.json` supplies `format`, `cpu`, and `machine` module IDs, each with `ANALYSIS_ABI=1`. `format.inspect(source)` recognises a file structure, a load window and architectural seeds; `cpu.decode(fetch,pc)` validates instruction length and flow and supplies limited abstract effects; `machine.initial`, `resolve`, `transition`, `inventory` and `probes` implement image-specific mapping. Registered provider source hashes are included in each analysis receipt. Provider entrypoints are restricted to the package's plugin namespace; a registry edit cannot load arbitrary Python module paths.

The format/CPU/machine boundary is **separate from the native DLL API**: this first version is an offline Python analysis-provider implementation. Replacing it with native provider-backed semantics should not require changing the compiled controller or universal report contract. It must not be described as a completed multi-console recompiler.

| Registered format | ISA | Mapping | Current static limits |
| --- | --- | --- | --- |
| SMS `TMR SEGA` cartridge | Z80 | Banked 16 KiB windows, known mapper writes tracked | Unknown indirect targets, instruction-level abstract state and unverified orphan banks |
| Mega Drive cartridge header | Motorola 68000 | Flat cartridge reset-vector window | Conservative subset of control transfer and basic words; unrecognised variable-length instructions fail closed |
| PS-X EXE | MIPS R3000A | Executable load address/payload | Static 32-bit opcode subset and branch delay slots; BIOS, disc files, overlays and GTE not implemented |

Unknown console ROM formats, other mapper types, compressed/encrypted executables, PS1 disc images and dynamically generated code need additional providers. **Do not** guess based on a filename or silently interpret the bytes as Z80.

## Evidence contract

`analysis.json` uses schema `recompdev.offline.analysis.v1` and records source SHA-256, plugin source hashes, CPU/machine profile, entry seeds, static candidates, honest unresolved reasons and source-size classification. `instructions.json` contains physical source offsets, guest addresses, exact instruction byte hashes and flow candidates. `bank-inventory.json` covers all provider-declared source regions and makes no claim that unvisited banks are non-code. `orphan-hypotheses.json` is an explicitly **unverified** set of entry guesses; it is not trusted by the native translator. `unresolved.json` enumerates unknown mappings, unsupported instructions, dynamic targets, budget exhaustion and conservative memory-alias warnings. Artifact hashes accompany the manifest.

There are no absolute semantic reachability claims. An instruction being source-attested does **not** prove it executes at runtime; a generated static graph does **not** prove exhaustive code discovery. To feed a candidate into the native translator, a future CPU plugin must provide a **separately verified translation** and an exact CPU/source/mapper/entry context. Standalone export readiness and game/hardware parity are always false in this version. The existing v0.4.9.34 exporter remains usable, but is not wired to this unqualified analysis.

## Non-regression and extension rules

Adding another platform requires a new format/provider registration with independent tests. The universal `engine.py`, compiled controller and CLI must not accumulate platform switches. Preserve existing generated native source history, Windows runtime slots, all frozen histories and previous evidence. No bundled commercial ROMs; use newly authored fixtures for automated acceptance.
