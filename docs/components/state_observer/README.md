# state_observer — generic guest-memory observation

**Version:** 0.1.0. **Scope:** `production-diagnostics`, registered independently in `workspace/components.json`.

A replaceable machine provider supplies one or more read-only `MemoryRegionView` descriptors: stable region ID, provider ID, address space, guest base, byte pointer and byte count, byte order and clock domain. The recorder never interprets CPU opcodes, bus/register semantics, input buttons, VDP rules or game-specific RAM addresses. Regions are provider-chosen spans, so 68000, MIPS or multi-CPU hardware can use the same contract with their own adapters. Provider-specific clock domains are kept separate; directional correlation is attempted **only** when the caller supplies a compatible input clock domain.

**Current provider:** `movement_trace/bridge/rd_sms_memory_adapter.hpp` supplies Sega Master System Z80 work RAM, physical 8 KiB at `0xC000` (mirrored addresses are not duplicated). No MD or PS1 provider is claimed yet.

**Output:** `state-memory-regions.csv`, `state-memory-deltas.csv`, `state-memory-summary.csv`, `state-memory-diagnostics.json`. First observation records a baseline with previous=-1. Subsequent samples record byte changes and preserve source-region metadata. Sampling is at guest render/frame boundaries, not every guest memory write. The analysis ranks **unidentified candidate byte offsets** by activity and conditional correlation; it NEVER labels an address as player X/Y, camera, collision or health without independent verification.

**Limits:** opt-in through `RECOMPDEV_STATE_TRACE_DIR` (set by `-MovementTrace`); <=64 regions, <=64 KiB/region, <=256 KiB aggregate, <=36,000 samples, <=2 million delta rows. At configured limits the observer marks a truncated trace and does not alter the guest. Files are external evidence, not tracked source or ROM dumps. RAM values may be sensitive in other applications; don't publish raw traces without checking them.

**Validation:** compiled C++ tests with unrelated multi-region multi-clock providers, synthetic SMS adapter, delta-chaining integrity checks and previous movement tests. Native Shinobi correctness, reference-emulator comparison, and exact player-state identification are pending.
