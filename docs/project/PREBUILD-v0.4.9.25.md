# PREBUILD v0.4.9.25 — Owner-approved universal artifact retention

**Date:** 2026-11-08. **Owner instruction:** Build a futureproof, cross-CPU and cross-hardware retention system; eliminate indefinite dependency on past diagnostic reports. This is an **infrastructure-source** scope under [DEVELOPMENT-CONTRACT.md](DEVELOPMENT-CONTRACT.md) and the previously binding [PREBUILD-v0.4.9.7.md](PREBUILD-v0.4.9.7.md). Main source promotion only after full owner Windows tests; native runtime activation is forbidden until separately accepted.

## Scope and acceptance

- Universal native artifact service with versioned ABI, binary content hashes, producer/target/ABI descriptors and strict bounds, with no Z80/SMS schema built into storage.
- Atomic retention of actual source-attested reusable analysis and translation-source inputs, automatic migration from v23/v24 owner evidence, automatic use in new jobs, source-independent portable evidence root and no rewrites of old records.
- Synthetic MIPS and 68000 producer contracts; synthetic Ghidra and source-verified bank overlays must replay after deleting old evidence and moving cache.
- Owner Windows 81/81 CTests, all frozen 642 files unchanged, and two real ROM migration/replay tests. Only after successful migration may old evidence stop being required for the migrated input; never recommend blind deletion.

## Approval and BLOCKED qualification

Approval covers **Git main infrastructure source only** (`git-main-only-no-runtime`). **BLOCKED:** compiled game-binary reuse, dynamic in-process hot-loading of machine code, complete guest-state continuation, independently referenced input/video/audio/CPU parity for Shinobi, live native executions for Mega Drive/PS1, and hardware-independent executable compatibility across unlike host ABIs. A capsule is replay input, not executable authority. Only CPU-specific plugins may validate their own instruction semantics. The target must never claim that a 960-frame neutral run proves parity.
