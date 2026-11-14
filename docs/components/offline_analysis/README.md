# offline_analysis — interchangeable static whole-input discovery

**Component:** `offline_analysis` (registered in [workspace/components.json](../../../workspace/components.json))

**Scope:** `production-workflow`. Versioned, *static and bounded abstract-state only* plugin provider chain; the universal engine knows neither cartridge format, CPU instructions nor console memory maps. It never starts a game or downloads analysis tools. Files are source-bound SHA-256 evidence, not executable native code.

## Stable owner interface

```powershell
& $exe analyze --rom 'C:\Roms\example.sms' --out 'C:\Projects\RecompDev-Evidence\offline-v36-example' --budget 40000
& $exe analyze --profiles
```

The same command and report schema apply regardless of image type. `--profile` chooses only a registered profile and **does not force** a wrong format to be decoded. On supported inputs, a successful static-analysis run returns 0; unrecognised inputs return 2 with an explicit `UNSUPPORTED_FORMAT` manifest; invalid/unsafe input or output returns 3. The parent of a fresh output folder is created automatically. The output folder must not exist. Inputs are not modified; symlinks are refused. The process is bounded by 64 MiB per source and 100,000 static instruction candidates, and rejects decoding outside provider-attested source bytes.

## Interchangeable plugin boundary

`profiles.json` supplies `format`, `cpu`, and `machine` module IDs, each with `ANALYSIS_ABI=2`. `format.inspect(source)` recognises a file structure, a load window and architectural seeds; `cpu.decode(fetch,pc)` validates instruction length and effects, while `cpu.initial(image)`, `cpu.key(facts)`, `cpu.advance(instruction,facts)` and `cpu.indirect(instruction,facts)` own ISA-specific abstract register constants and control-flow target resolution. `machine.initial`, `resolve`, `transition(image,instruction,mapping_state,cpu_facts)`, `inventory` and `probes` own address mapping and memory-mapped hardware effects. The universal engine alone owns bounded call/return contexts and branch/delay-slot ordering. Registered provider source hashes are included in each analysis receipt. Provider entrypoints are restricted to the package's plugin namespace; a registry edit cannot load arbitrary Python module paths.

The format/CPU/machine boundary is **separate from the native DLL API**: this first version is an offline Python analysis-provider implementation. Replacing it with native provider-backed semantics should not require changing the compiled controller or universal report contract. It must not be described as a completed multi-console recompiler.

| Registered format | ISA | Mapping | Current static limits |
| --- | --- | --- | --- |
| SMS `TMR SEGA` cartridge | Z80 | Banked 16 KiB windows, known mapper writes tracked | Only statically provable indirect register targets, limited register arithmetic and unverified orphan banks |
| Mega Drive cartridge header | Motorola 68000 | Flat cartridge reset-vector window | Conservative subset of control transfer, MOVEQ, LEA and An indirect flow; unrecognised variable-length instructions fail closed |
| PS-X EXE | MIPS R3000A | Executable load address/payload | LUI/ORI/ADDIU constants, register jumps, return links and ordered delay slots; BIOS, disc files, overlays and GTE not implemented |

Unknown console ROM formats, other mapper types, compressed/encrypted executables, PS1 disc images and dynamically generated code need additional providers. **Do not** guess based on a filename or silently interpret the bytes as Z80.

## Evidence contract

`analysis.json` uses schema `recompdev.offline.analysis.v1` and records source SHA-256, plugin source hashes, CPU/machine profile, entry seeds, static candidates, honest unresolved reasons and source-size classification. `instructions.json` contains physical source offsets, guest addresses, exact instruction byte hashes and flow candidates. Newly reported `classification` explicitly distinguishes ordinary static candidates from speculative caller fallthrough hypotheses; neither is proof of semantic correctness or executable reachability. The `abstract_execution` section accounts for resolved return sites, indirect sites, decoded delay slots, abstract contexts, speculative candidates and the ABI version. `bank-inventory.json` covers all provider-declared source regions and makes no claim that unvisited banks are non-code. `orphan-hypotheses.json` is an explicitly **unverified** set of entry guesses; it is not trusted by the native translator. `unresolved.json` enumerates unknown mappings, unsupported instructions, dynamic targets, budget exhaustion and conservative memory-alias warnings. Artifact hashes accompany the manifest.

Return-stack inference is bounded (16 nested calls), context exploration is capped, and branch flags are not symbolically solved. Unknown callees are explored speculatively with cleared CPU constant facts; they must never be treated as confidently reachable. The Shinobi smoke scan may enumerate *fewer* instruction candidates than v0.4.9.35 because v2 is deliberately more conservative. There are no absolute semantic reachability claims. An instruction being source-attested does **not** prove it executes at runtime; a generated static graph does **not** prove exhaustive code discovery. To feed a candidate into the native translator, a future CPU plugin must provide a **separately verified translation** and an exact CPU/source/mapper/entry context. Standalone export readiness and game/hardware parity are always false in this version. The existing v0.4.9.34 exporter remains usable, but is not wired to this unqualified analysis.

## Non-regression and extension rules

Adding another platform requires a new format/provider registration with independent tests. The universal `engine.py`, compiled controller and CLI must not accumulate platform switches. Preserve existing generated native source history, Windows runtime slots, all frozen histories and previous evidence. No bundled commercial ROMs; use newly authored fixtures for automated acceptance.

## v0.4.9.37 extension: memory effects, comparative evidence and native control-flow witness

`--compare-to PREVIOUS_ANALYSIS_DIRECTORY` can be repeated (up to eight baselines). Each baseline's SHA-256 source identity and instruction file digest must match before a comparison is published. `regression-comparison.json` (single) or `regression-comparisons.json` (multiple) gives exact `(pc, physical, length, bytes_sha256)` retained/new/missing identities and any confidence reclassification, without asserting improved code coverage. A missing, mismatched, symlinked or tampered baseline fails closed before writing the output.

The source+CPU+machine plugin chain now distinguishes definitely safe stack writes, signed IX/IY displacements, block-copy byte ranges and writes to mapper control or bank registers. A copy count of zero represents a full 65,536-byte LDIR/LDDR traversal. Unknown destination/counts still invalidate bank knowledge. AbstractFacts joins retain only equal constants on *all* speculative incoming paths, and mappings are never merged across different physical banks. MIPS untaken branch-and-link paths and 68000 exception return contexts are treated conservatively. These are **partial instruction semantics**, not a certified full decoder or emulator.

The new **experimental**, optional `RecompDev.exe analyze-native --rom FILE --analysis DIR --out NEW_DIR --rights-confirmed` route produces a source-attested CMake project containing native C++ control-flow cases for select **non-speculative, byte-hash-verified** candidates. Each CPU provider must explicitly implement `lift_probe(raw,pc)`; the generic controller and code generator contain no CPU opcodes. Z80 supports only NOP, JP, JR, HALT and M68000 only NOP, BRA, STOP. Other CPU providers return `PROBE_CPU_LIFTER_UNAVAILABLE`; unsupported instructions are omitted and execution stops `UNTRANSLATED_PATH` if reached. It is not a full semantic CPU translator or the existing production game-native exporter, and exposes no video/audio/input/timing hardware. C++ compiles via the host's own CMake toolchain for authored proof fixtures. The original source file is not needed to execute the resulting proof EXE. The v34 standalone exporter continues separately and unchanged.

A released controller built as source-only is under the release transaction `cmake/bin[/Release]/RecompDev[.exe]`; the active runtime is **not** automatically replaced. See [v37 release](../../releases/v0.4.9.37.md) for owner acceptance and blocked gates.

## v0.4.9.38 extension: ISA semantics and arithmetic-state native proof

The same CPU provider interfaces now emit known Z80 partial bytes, 16-bit arithmetic, interrupt modes, ED I/O repeat effects and CB bit/rotate effects without unnecessarily invalidating SP or mapper mapping. The machine provider alone interprets whether a declared RAM write aliases mapper registers. Motorola 68000 and MIPS independently gain more exact constant-register and known address computations; MIPS ADDI overflow or unknown signed overflow is reported as an unresolved instruction context. Unqualified/unsupported instructions are **not** silently promoted.

Optional `lift_probe(raw, pc)` can now return a bounded **native register operation** with `kind=reg`, `register`, `width` (8, 16 or 32), `op` (set/add/and/or/xor), and immediate `value`. The generic code generator validates these fields and emits C++ switch cases and synthetic register outputs, with zero-initialized probe-only registers. `lift_probe` remains explicitly ISA-owned; no opcode table exists in the controller. Only the independently proven Z80 A and 68000 Dn fixture subset is accepted, not arbitrary instructions. The standalone output remains a **proof program**, not a playable native game or a complete CPU machine-state implementation. Unknown control-flow paths stop with `UNTRANSLATED_PATH`. All prior source-file, provider-source, candidate-byte, classification and rights checks still apply.

Owner Windows acceptance now requires 111 CTests, original historical file preservation, source governance and rollback backup. This is a source-only candidate; no automatic runtime activation or remote push. [Release record](../../releases/v0.4.9.38.md).
