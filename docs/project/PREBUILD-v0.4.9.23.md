# Prebuild specification — RecompDev v0.4.9.23

**Date:** 2026-11-08. **Owner-approved request:** build next increment and supply safe longer Shinobi/keyboard test commands. **Baseline:** installed `workspace/v0.4.9.22` main `9299590078ae5f8af547e2d7733fc428394d83f9`, owner 74/74 Windows CTests, 642 original files preserved; no runtime activation. **Track:** `infrastructure-source` / `git-main-only-no-runtime`. Read [development contract](DEVELOPMENT-CONTRACT.md), original [PREBUILD-v0.4.9.7.md](PREBUILD-v0.4.9.7.md), [handover](HANDOVER.md).

## P0 functional change boundaries

1. **Architecture-neutral COMPAT-023:** Accept exact `b'\x1b[2K\r'` array preamble from Rizin on Windows; newline/warning fixture stays valid. Do not normalize arbitrary prefixes, drop malformed diagnostics or edit captured raw logs. SHA-256 identity, maximum records, strict JSON duplicate/trailing/size checks, explicit audit remain. Test CPU-independent provider API. This removes a pre-round parser stop in Alex Kidd and Bank Panic; their valid code/execution/parity remains unproven.
2. **CPU-neutral telemetry:** Explicit watched PC/range hits counted once each but high-frequency repeated values use early examples, ordinary stride instruction records and periodic/final counted summaries; no false every-hit trace guarantee. Bounded per-PC counters, total and coalesced hit fields, audit in ROM-free diagnostic ZIP, 180k instruction-sampling ceiling reserving essential event allowance from 200k total cap. No game-loop modifications, CPU-specific rules or hidden unlock of recovery.
3. **Controller-owned live display:** On-disk sampled JSONL remains preserved, while a separate 1-in-16 instruction live-display sampler protects subscriber transport; stop/frame/input/notice/summary bypass display sampler. Report actual display transport losses separately, never claim zero loss without owner evidence. Native monitor viewer remains read-only Win32 C++.
4. **Evidence lifecycle:** Seal final aggregate before native preview returns, on source-attested private generated frontend only. No change to immutable source translation or owner ROM, original jobs, active DLLs, legacy or baselines. ROM-free upload ZIP remains hash verified.

## Acceptance and known unresolveds

- Cross-platform: exact CR fixture and unknown-ANSI/CR negative tests; synthetic 120,000-hit queue stress and 1,600-event display decimation contract; unchanged v22 native preview and controller suite.
- Owner Windows: all 76 CTests, governance, 642/642 hashes and source-checkpoint + rollback backup; then fresh Alex Kidd / Bank Panic run, verifying `rizin-aflj.json`, `rizin-provider.json`, and at least one *orchestration round*, or truthful newly observed provider rejection. Do not overwrite previous read-only diagnostic jobs.
- Preserve 71 shared CALL-site target-agreement baseline, but 215/12 Rizin-only outside Ghidra bounds remain *analyzer hypotheses*. `functions_qualified:false` was not proven an additional failure. Game parity/input/VDP/audio/mapper, long Shinobi and full second-ROM native gameplay unqualified.
- Fixing Win32 C4312 control-ID casts is non-blocking but not in this bounded scope; include in future hygiene release, without introducing untargeted UI mutations.
