# Next integrated RecompDev build: architecture and acceptance

## Owner naming state
Ridge Racer is already manually labelled in the Workbench. Do not re-run name sync or overwrite the alias; any future automatic identity data should be a separate evidence record.

## Existing baseline (owner Windows evidence, not rerun here)
- RecompDev Catalogue v0.2.1.1 Workbench: 3 registered targets, 17,866 seed-reachable instruction observations, 309 static function-entry candidates, 659 call sites and 107 unresolved barriers.
- Systems: Mega Drive / M68000 (Sonic and Streets of Rage 2) and PlayStation / MIPS (Ridge Racer extracted PS-X EXE).
- Earlier RC9326 source patches include 68000 instruction forms and Windows-Go source/launcher identity fixes; preserve and independently regression-test them. This bridge package does not modify those sources.

## What is implemented in this bridge
1. Metadata-only identification adapters: Mega Drive cartridge header; PS-X EXE project context; simple PS1/PS2 ISO9660 Mode1 / SYSTEM.CNF; standalone Xbox 360 XEX2 and STFS header; standalone PARAM.SFO. Unhandled containers remain explicit.
2. Source-identity-bound SQLite naming preview and optional backed-up update. User aliases and publisher header names are not blindly replaced.
3. Read-only per-candidate conversion readiness from SQLite; prioritize by unresolved function boundaries and instruction form frequency. Avoid metrics that conflate graph nodes with complete functions.
4. Adapter capability registry detailing implemented vs planned support, including PS2 and Xbox 360.

## v0.3 integrated platform design

```text
local binaries/discs -> format recognizers (format, sections, ID)
                     -> file-system/container loaders (checked offsets, overlays)
                     -> ISA decoders and execution semantics (per CPU)
                     -> provenance-preserving discovery (Ghidra/Rizin/Capstone/dynamic traces)
                     -> canonical function CFG/IR (calls, data effects, indirect targets, ABI)
                     -> persistent shared catalogue + confidence/evidence graph
                     -> capability negotiated batch conversion -> isolated C++ toolchain
                     -> independent reference executor comparisons -> acceptance/retry
```

The core must not import game/console names, nor contain emulator gameplay loops. Platform-specific MMIO and timing are *guest services* or reference test adapters, not an emulator inside RecompDev. Return/wrapper model and source licensing must be audited.

## Required next implementation (not built in this package)
- Complete metadata/loader stack: multi-track CUE/BIN PlayStation, ISO9660/Joliet and PS2 dual-layer ISO handling; PS2 EE/IOP ELF; Xbox 360 XDVDFS and XEX image mapping; later more systems via same interface. Do not promise extraction of protected/encrypted payloads.
- Title lookup: versioned, licensed serial/Title ID reference datasets, cached results, multiple-match ambiguity, cross-validation against payload hashes. No arbitrary search results promoted into verified names.
- Canonical IR: explicit `arch`, `word width`, `PC`, `instruction SHA`, byte span, 0..N successors, flags, register defs/uses, ordered guest-memory transactions, exceptions, delay slots, endian/ABI/return contract and unknowns.
- Function recovery: direct and indirect call targets, tail calls, interrupt vectors, overlays, calls across dynamically loaded modules; keep uncertain boundaries explicit. Static 309-entry count is *not* 309 source-complete functions.
- Capability and C++ generator adapters: `decode -> lift -> validate -> emit -> compile -> differential-test -> accept`, with independent CPU reference oracles. Semantics capabilities versioned by ISA/operand form, not game; unsupported operations fail closed.
- Batch campaign: scan all registered targets, group missing capabilities across all games, parallel sandbox jobs, prioritize common semantic requirements, replay blocked functions after one shared fix, preserve immutable evidence.
- Workbench: retain single page and tabs; add `Identity`, `Batch conversion`, `Evidence provenance`, `Capability gaps`; show true stages separately (discovered, boundary-qualified, lifted, compiled, differential parity, runtime dispatched).

## Acceptance tests for next substantial release
1. Automatically name Sonic, Streets of Rage 2 by headers and Ridge Racer via verified disc ID+catalogue or marked project hint without manual alias.
2. Add PS2 metadata and Xbox 360 metadata test fixtures without changing shared database schema or scanner core.
3. Analyze two Mega Drive games and one MIPS program from an unchanged core entrypoint and produce a unified function/call graph.
4. With owner-local inputs, generate C++ from at least one **fully bounded** function per supported ISA; compile; compare outputs against independently executed guest instructions and bus records. Report partial/blocked faithfully.
5. Run a multi-target batch reusing a verified semantic implementation across two different games without game-specific source edits.
6. Fail closed for missing ROM bytes, mismatched SHA, unsupported XEX payloads, unresolved function boundaries, missing CPU semantics, and unverified hardware I/O.
7. Owner Windows tests, full Go suite, source hash verification, SQLite migration rollback, launcher binary identity checks, versioned handoff and no proprietary ROMs inside distribution.
