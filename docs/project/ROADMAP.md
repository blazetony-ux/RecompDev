# Current roadmap and acceptance gates

## v0.4.9.22 UI and second-ROM evidence

Native monitor UI scheduling, bounded queue overflow reporting, exact sample-independent logical-PC watches and search/follow are implemented in source candidate v0.4.9.22; Linux CI/build and owner Windows full acceptance gates apply. Test real Win32 responsiveness under 1,800-frame Shinobi traffic and run independent, small-budget ROM smoke jobs. Do not claim second-ROM compiled support until genuine source-attested outcomes exist. Independent reference-emulator replay/input/audio/video/state checks and full legacy migration remain blocked. [Release](../releases/v0.4.9.22.md).


## v0.4.9.21 — native monitor and explicit parity gates

The owner reached 1,800 native host output frames on original Shinobi with a source-verified v0.4.9.20 recovery job; the target is **frame-count only**, without deterministic gameplay/input/audio/reference parity. The next candidate introduces a genuine independently compiled Win32 C++ read-only monitor, a CPU-neutral data comparator, terminal guest/device/host frame counter separation and bounded 128-cycle automatic recovery. **Independent trusted emulator capture, real input replay and CPU/VDP/PSG/interrupt parity remain BLOCKED.** Do not add game-specific controller hacks, replace pinned old DLLs or declare native parity qualified. See [release](../releases/v0.4.9.21.md).

## v0.4.9.18 — evidence closure and targeted recovery infrastructure (2026-11-07)

## v0.4.9.20 — guarded native preview handoff

The owner v0.4.9.19 observed PC `0xADAF` and 936 host frames without pressing Z. This candidate adds a complete source-attested optional preview gap, direct controller `resume --preview-stop` preflight, native plugin-byte recheck and immutable history import. Host and guest frame counters are displayed separately, without claiming parity. 1,800-frame gameplay and multiple console/ISA qualification remain outstanding. See [scope](PREBUILD-v0.4.9.20.md).

Source-only work from published v0.4.9.17 `main`: versioned evidence-root job/diagnostics routing; immediate-history Ghidra/Rizin reuse only after ROM, tool and provider hash re-attestation; newest imported stop prioritized; compact source-matched per-cycle translated-PC/physical-address differences in ZIP. Owner evidence v0.4.9.16 cycle 2→3 showed two new code addresses but no frames beyond 896. **Next:** owner Windows installer validation and real Ghidra/Rizin run to measure cache hits, time/cycle savings, stagnation, then independent correctness tests. Never equate extra code or frames with gameplay parity. See [prebuild](PREBUILD-v0.4.9.18.md).

## v0.4.9.16 — accumulate authenticated recovery, not shell commands

Following v0.4.9.15 owner 60/60 Windows acceptance and genuine Shinobi two-session 64-frame job, v0.4.9.16 retains earlier imported evidence rather than discarding it between batches. **Real-ROM acceptance still pending.** Future work: second ROM, graphics/audio/input parity, 1,800-frame target, complete native provider ABIs and zero active frozen dependencies. No broadening into ROM-specific patches. See [prebuild](PREBUILD-v0.4.9.16.md).

## 2026-11-06 — native existing-functionality migration

- **Implemented in v0.4.9.9 source candidate:** controller directly executes existing hash-verified P-code game DLL through shared native harness runner; Z80 source decoder now recognises documented prefixed opcodes; original SMS mapper state is used via hardware DLL. Linux acceptance does not establish Shinobi gameplay parity.
- **Next mandatory port, not complete:** native translation backend that accepts source-verified Ghidra P-code exports from multiple machines, replacing transitional Python generator; source-evidence-preserving runtime recovery and full Z80 state/interrupt semantics. Windows multi-ROM acceptance is pending. Do not substitute further reporting infrastructure for working executable paths.


**Status:** Current. Last reviewed: 2026-11-05.

## Completed and demonstrated

1. Historical-source preservation gate: 581 v0.4.0.45 files and 61 harness v0.3 files verified unchanged.
2. Compiled controller capable of invoking preserved Python discovery, preparation and continuous native recovery.
3. Owner-reported Shinobi session advanced to 120 frames after three bounded recovery rounds; **gameplay parity not established**.
4. Permanent v0.4.4 Git workspace with independently versioned and deployed harness DLLs, external output directories and Windows tests.
5. v0.4.5 adds documentation governance; no new CPU or hardware functionality.

## Next engineering milestone: production plugin integration

Demonstrate that changing an independently built Z80 CPU, translator or Master System plugin affects **real production instruction processing** via a documented, versioned contract, without rebuilding the controller or altering the preserved legacy source. Retain validated fallback, record plugin identity/hash in per-run evidence and prove a rollback. No synthetic-only substitution is sufficient.

## Later work, not yet validated

- Hardware-state capture at source (selected-frame raw VRAM, CRAM, VDP register and timestamped PSG traces).
- Independently aligned video/audio/interrupt parity on Master System ROMs beyond the synthetic harness.
- Correct silence diagnosis, asset extraction and eventual ROM-independent generated game executable.
- Proper CPU/translator and machine plugins for Motorola 68000/Mega Drive and MIPS R3000A/PS1.

## Cross-game acceptance

Avoid progress measured only in Shinobi instruction counts. Validate at least two additional Master System titles with source-attested behavior, and report failures as carefully as successes. Use the shared controller and plugin APIs rather than per-game branches.

## Phase-1 outcome, workspace v0.4.6

Versioned CPU DLL admission of authentic Z80 bytes is now wired into the real recovery hand-off; it is source validation only. Next, migrate the native instruction translation/execution interface so a swapped component changes emitted native C++ behaviour and hardware correctness can be validated independently. Machine/VDP/PSG plugin adoption remains pending. Continue using small, reversible Git patches and never modify frozen legacy baselines.

## v0.4.7 next acceptance gate

The complete old generator is now selected via a source-versioned production adapter rather than rewritten. Before claiming recovered 600-frame progress under the modular workspace, reproduce the historical Shinobi run with matching ROM hash, deterministic input, requested frame count and recovery limits, then compare stop reason, native steps, frame/PSG/VDP counters and captured images against preserved evidence. Use the read-only Workbench to inspect catalogue contents without changing the owner's database. Further hardware plugin extraction remains staged behind these regressions.

## Native game follow-through after v0.4.8

1. Verify generic host window/input on the previously compiled source-authenticated 600-frame Shinobi native project; inspect its automatic evidence ZIP, without assuming that Start reaches gameplay.
2. Diagnose input-to-guest button semantics, missing code and silent audio using the preserved engine; fix in the appropriate reusable plugin.
3. Separate original ROM data dependencies from compiled native code and source-derived assets, then test without the ROM. Do not claim ROM independence until explicitly demonstrated.
4. Reuse this unmodified host API with a second platform-specific native execution module when available. Keep machine-specific implementation entirely outside the presentation component.

## v0.4.9 input-driven native gameplay route

The original 600-frame Shinobi milestone has been re-established with the preserved production translator. A native Windows window and Button 1/Z title transition were demonstrated; the guest then stopped at untranslated `0x7BE8`, frame 201. The next priority is bounded deterministic guest-cycle replay of that input and source-authenticated recovery of the missing path, then retest the generated game without rebuilding unrelated DLLs. Existing v0.4.8 wall-time input logs must be labelled estimated and the initial stop reproduced before recovery. If that fails, capture an exact guest-cycle trace using the v0.4.9 runtime frontend and retry. **Playable stage, sound correctness and ROM-free packaging remain unproven.**

**v0.4.9.1 engineering fix:** Short external CMake build paths and source-verified recovery-history reuse; validate on Windows before claiming gameplay advancement.

## Native video acceptance following workspace/v0.4.9.2

First inspect a Windows native Shinobi run with `rd_video_sms_mode4` active. Require loaded plugin version/hash, `sms-sprite-stats.csv` SAT activity and visible character/enemy pixels before claiming real gameplay graphics. Independently recover the `0x1E62` guest code path using the existing input-recovery engine. Later qualify video accuracy against independent hardware/emulator traces, including sprite status and scanline effects; do not rewrite the generic host or original translator for video behaviour.

## Movement observability milestone — v0.4.9.3

Shinobi's apparent mid-session movement reversal is an unresolved accuracy issue, separate from the `0x1E09` untranslated-code stop. The immediate milestone is a controlled Left/Right guest-cycle trace proving whether the observed input differs at the host, console I/O, guest state, or display layer. The new `movement_trace` component records real guest DC/DD reads and per-frame raw SAT/scroll values; this enables a diagnosis but is deliberately not a speculative controls fix. Later milestones: reference emulator comparison of hardware timing/sprite priority, controller accuracy across consoles, sustained gameplay coverage, audio playback and ROM-independent output.

## v0.4.9.4 diagnostic provider contract (2026-11-05)

The owner requires all components **decoupled and interchangeable**. Guest-state telemetry uses a generic independently versioned `state_observer` memory-region interface; it must never contain Master System `State::ram`, Z80 instructions or Shinobi RAM address assumptions. `movement_trace` 0.2.0 owns the first SMS-only 8 KiB provider; Mega Drive and PS1 would each supply their own provider without rewriting the common recorder. Correlation only compares inputs and memory changes when the provider's cycle domain matches. Current 2400-frame Shinobi evidence shows correct guest controller reads but intermittent unresponsive movement; memory diagnostics do not fix it, and actual Windows evidence and independent emulator comparison remain necessary. Historical translator and active DLLs are unchanged. See `docs/releases/v0.4.9.4.md` and `docs/components/state_observer/README.md`.

## v0.4.9.5 — completed source implementation, Windows acceptance pending

Controller-mediated live execution monitor via `controller_diagnostics` event ABI and separate viewer; no direct plugin dependencies, staged guest source retained byte-identically. Follow-up gates: prove two-window Windows session; recover idle title path 0xB2E1; add CPU-provider decoding metadata through plugin APIs; implement optional controller-mediated pause/step/breakpoints only after guaranteed native safe points; prove game/reference movement parity.

## Workspace v0.4.9.6 — discovered capabilities and open work (2026-11-05)

- Delivered source-only controller discovery audit v1 with versioned, registry-selected legacy structure / catalogue / ISO-sector adapters and conservative fresh/cached status. It cannot silently equate `DISCOVERY_COMPLETE` to new instructions/assets.
- Preserved historical Master System, Mega Drive and PS1 implementations and 642 frozen source files; no active CPU/video/runtime DLL changed. Revalidate existing 44 CTests on owner Windows before accepting the release.
- **Carry-forward Shinobi gate:** last interactive Right-input run ended at untranslated `0x4F9E` about frame 730 with player-observed reversed scrolling. Do not patch a game address or declare VDP scrolling broken from a wraparound R8 observation. Independently validate instruction semantics, bank/interrupt timing and video output while retaining earlier 1,800/2,400-frame observations as non-parity evidence.
- **Next:** source-targeted scheduling/recovery, reusable IR and 68000/MIPS active plugin integration, more verified asset/container readers, multi-input synthetic and real-ROM regression campaigns. Do not confuse source detection, candidate extraction and parity.

## v0.4.9.7 candidate — native-first architectural and discovery milestone

Approved scope and hard acceptance gates: [pre-build report](PREBUILD-v0.4.9.7.md), [development contract](DEVELOPMENT-CONTRACT.md). Native C++ `RecompDev` discovers format and source Z80 blocks through DLLs. Before installing/promoting, still require real Master System source-attested P-code translation and compilation, owner Windows regression results, and Shinobi smoke/continuity evidence. All incomplete items remain BLOCKED rather than being renamed as success. Next accepted build should integrate actual CPU-to-native backend invocation and controller recovery, not another script-based audit.

## v0.4.9.8 candidate — release protocol consolidation

The permanent Git-controlled `Install-RecompDev-Release.ps1` with externally SHA-256-pinned source ZIPs replaces per-release installers. Owner Windows validation, 45 CTests and the real SMS ROM -> preserved P-code -> native C++ acceptance are still required before promotion. This protocol amendment is release infrastructure, not a new game-facing feature. Preserve the earlier native discovery candidate and the Shinobi monitor, recovery and unresolved parity limitations. See [prebuild amendment](PREBUILD-v0.4.9.8.md).

## Owner-requested v0.4.9.8 installation gate (2026-11-06)

The Windows owner has passed 45/45 native CTests, docs/Python checks and original 642/642 frozen histories in `Validate` mode. As explicitly requested, v0.4.9.8 is re-scoped as an **installable native-discovery milestone** (controller + SMS/MD/PS1 format plugins + conservative Z80 and SMS extensions + permanent Git-managed release script). The next activity is to exercise `Install` end to end and verify actual Git commit, `workspace/v0.4.9.8` tag, verified bundle and active binary SHA lockfile. Only then begin the real-ROM source block -> full preserved P-code -> native C++ build integration as the next milestone. Re-scoping release acceptance is not a claim that native translation is implemented.

## v0.4.9.10 — compiled P-code translation migration (candidate, real-ROM gate BLOCKED)

Compiled controller and `rd_translation_pcode` DLL now generate and build the full preserved nativepilot application or interchangeable game DLL from source-verified Ghidra exports. Fixture differential against original generator passes locally. The mandatory next acceptance is owner real Shinobi original ROM plus original authentic Ghidra base export and old bank recovery evidence, fresh native compilation through the new controller, then deterministic execution compared with observed 1,800-frame legacy run and a second Master System game. Until proven, auto-recovery, full Ghidra disassembly and hardware runtime plugin migration remain top priority, not new release engineering or generic monitor work. See [full release record](../releases/v0.4.9.10.md).

## v0.4.9.10 active SMS runtime cutover status (2026-11-07)

Compiled maintained SMS state/video/host boundaries are working on Linux synthetic fixtures. The real 120-frame Shinobi display predates this cutover; require a fresh Windows Shinobi native project with these independent DLLs, repeat 1,800-frame deterministic input and image comparison, verify a second Master System ROM, and finish replacing Python analysis/recovery services. Do not promote a synthetic-only candidate.


## v0.4.9.11 architectural integration and outstanding promotion gates (2026-11-07)

**Current:** Compiled controller starts authorized Ghidra/Rizin analysis providers via temporary source-only adapter; reconciled, hash-bound entries enter native CPU/mapper discovery, generated native project translation/build and bounded application-stop recovery. Verified by two synthetic ROMs, not two real games. **Next:** Windows real Ghidra/Rizin execution, native processor/platform provider ABI with zero hardcoded SMS/Z80 entrypoint in universal controller, persistent cross-run source-hash evidence index and whole reachable-bank discovery; verify autonomous 1,800-frame Shinobi plus second unrelated real ROM. Do not release based solely on manual single-instruction recovery. Full game parity, input/video/audio and native ABI remain BLOCKED.


## From v0.4.9.12 onward — compulsory legacy dependency exit (owner direction)

v0.4.9.12 only hardens Rizin serialization within the active provider boundary. The **next builds must eliminate dependency on frozen Python/scripts in production**, not merely wrap them again. Keep `legacy/` and `baselines/` immutable for reference/differential tests. Order work by verified interface and parity gates, not arbitrary version promises: (1) replace Rizin subprocess execution/authorization and aflj parser with an independently versioned native analysis-provider process ABI; (2) migrate Ghidra invocation, byte-attested P-code export and reconciliation into maintained native provider contracts, retaining Ghidra as an external analysis tool where needed; (3) move Python orchestration/recovery and evidence approval into compiled controller/native DLL providers; (4) eliminate active runtime imports from frozen modules and test with frozen tree intentionally unavailable while preserving independent differential tests. Require multi-CPU fixtures and real Master System regression before each cutover. Details and dependency inventory: [legacy exit plan](../architecture/LEGACY-EXIT-PLAN.md).

## v0.4.9.13 — Rizin independent provider and controlled Git checkpoint

Source candidate replaces the active archived Rizin runner and tool authorization with maintained subprocess, strict aflj+ANSI evidence and versioned Python contract, without altering compiled controller/plugin ABIs. The reported Windows `ESC[2K` issue is now covered by synthetic tests. Next acceptance: owner Windows Validate and real Ghidra/Rizin run under new evidence directory with correct source hash, then independent second-ROM and 1800-frame parity checks before promotion. Release source remains non-promotable until all mandatory gates pass. Preserve a separate Git development branch checkpoint to prevent lost uncommitted progress; never equate a checkpoint with installed stable binaries.

**Next architectural priorities:** RecompDev-owned Ghidra exporter and normalized IR/reconciliation, then compiled analysis-provider ABI and controller-native recovery scheduler; enforce zero archived production imports in staged production-execution tests while retaining all historic files for regression comparisons.

## v0.4.9.14 — recovery history import and Ghidra dependency reduction

Maintained Ghidra process/export/scripts, source-byte checks and reconciliation replace the frozen analysis imports in this component. Import prior stops/bank overlays through immutable evidence replay in new runs, not binary/process checkpoint restoration. Qualify owner Windows real Shinobi restart and second ROM; move iteration and import enforcement into the compiled controller/provider ABI, remove remaining frozen imports in production translation/discovery, then prove complete parity.

## v0.4.9.15 — controller-owned persistent jobs (candidate)

The native controller now accepts `run`, `resume`, `status`, `inspect`, `configure`, owns the persistent per-ROM job registry and automatically chains immutable verified analysis/translation/execute/recovery **batches** with source SHA and stagnation checks. The temporary Python per-batch analyzer adapter must be retired through a true compiled versioned provider ABI; logging is controller-structured JSONL today, not yet universal per-plugin event streaming. Owner v0.4.9.14 Shinobi verification showed improvement from 67 to 894 frames using 4 authenticated prior stop overlays; 1,800-frame target and gameplay parity remain unproven. Second unrelated real ROM, native analysis-provider ABI, zero-frozen-import gate and git-main promotion remain mandatory acceptance.

## v0.4.9.17 infrastructure track: consolidation and missing legacy integrations

New acceptance split: SHA-pinned source-only Git main/tag promotion after full Windows regression; 1,800-frame Shinobi/hardware parity remain independently blocked for game runtime. Controller workspace/evidence ZIP, read-only catalogue inventory and accountable migration register establish operator/migration baseline. Next: full compiled analysis provider ABI, asset provider contracts, verified catalogue import, multi-ROM campaign, controller-authorised Workbench and full legacy test coverage. Do not treat status `independent` as `qualified` until differential tests pass.

## v0.4.9.19 — native preview and controller-subscribed live execution (2026-11-07)

Restore the existing independent instruction window in the *current compiled-controller* workflow through `RecompDev.exe preview --job ID`. Preview rebuilds a source-attested copied native game outside the recovery session; in-window button press events and sampled instruction transitions publish through the generic controller diagnostics API, with upload-ready stop correlation ZIP under `RecompDev-Evidence/v0.4.9.19`. Linux native smoke demonstrates the bridge; owner Windows GUI and authentic Shinobi Z-key behaviour still pending. The 936-frame current real-ROM recovery frontier and the mandatory 1,800-frame parity qualification remain unresolved. Do not mistake video output or correlated input events for verified gameplay semantics.
