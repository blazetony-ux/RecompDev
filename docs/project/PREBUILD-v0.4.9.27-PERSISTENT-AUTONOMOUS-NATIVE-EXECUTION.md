# RecompDev v0.4.9.27 — Persistent Autonomous Native Execution

**Status:** OWNER APPROVED 2026-11-08; native ABI and synthetic hot-resume foundation implemented. Full one-command 2,400-frame Win32 acceptance **BLOCKED**, not promoted or installed. See [v0.4.9.27 release report](../releases/v0.4.9.27.md).

**Prepared:** 2026-11-08. **Governing authority:** `docs/project/DEVELOPMENT-CONTRACT.md`, §3. This proposal must be presented and explicitly approved **before implementation code is written**. If the scope materially changes, submit an amended report for approval before proceeding.

## 1. Exact starting point and evidence

- Canonical committed source baseline: `ff5d9dc589dbb948b56a6159482330c6d77404c9`, tag `workspace/v0.4.9.25` (as identified by the validated candidate's release manifest). The owner has not reported promoting the v0.4.9.26 source to Git `main` or activating its native runtime.
- Most recent owner Windows-validated source candidate: `RecompDev-v0.4.9.26-PreviewFrontier-WindowsFix-CANDIDATE.zip`, SHA-256 `d1ffe8655198926f9ff3ce6f9c3e4bbf2c1fde89c98ffe48ff51b1018b675e6a`, validated at transaction `20261108T175411Z-18912`: **82/82 Windows CTests passed, 642 historical files verified, `VALIDATED_NOT_INSTALLED`**. The candidate contains a cumulative 20-file source delta from the committed baseline. It is *not* automatically an installed v26 Git baseline.
- Shinobi owner evidence: source-attested replay progressed from an original translated-code stop at PC `0x052A` around 331 frames through five cumulative recovery rounds to 2,400 frames and 8,648 emitted instructions. Separate generated native app reached 2,400 frames with live input; SMS scrolling/display fidelity remains defective and independent gameplay parity is unverified. These are not same-process hot-resume results.
- Fantasy Zone `(USA) (Rev-A)` owner evidence: ROM SHA-256 `d529aa91cc0e540c4e3afdf8d946c02cb80765d280286da0a4e2125e2c443311`; first recovery yielded 1,890 emitted instructions, 76 frames, stop PC `0x0614`, status `MAX_RECOVERY_ROUNDS_REACHED`. `preview` opened and closed its windows after the untranslated stop; no successful autonomous continuation. Neither game may be special-cased in production.
- The present project uses versioned controller and plugin C ABIs; Python/Ghidra/Rizin remain temporary analysis/translation compatibility providers, *not* a compiled universal code-generation plugin. The existing `rd_runtime_host` ABI is presentation-only (`rd_host_present`, `rd_host_pump`, etc.). The native-app executable has its own execution lifetime. No complete guest-state-preserving native module activation exists.
- Frozen `legacy/` (581 original files) and `baselines/` (61 originals) remain byte-identical; original ROMs, historical sessions, recovery evidence, owner-local catalogues, and active binaries are immutable inputs. No new top-level `C:\Projects` directory is permitted.

## 2. Owner-requested outcome and non-negotiable scope

**One ROM, one invocation, two persistent windows, autonomous translation.** For a previously unseen, supported Sega Master System ROM, the user starts the controller once. The controller opens the **actual** native execution monitor and game display and keeps both open as analysis/compilation and execution proceed. When native execution encounters untranslated guest code, the same session pauses, reports a recoverable typed frontier, compiles or retrieves a compatible native block module, safely activates it, then resumes **without resetting the guest state, closing/reopening the windows, or requiring a manual `resume` or another job command**. Continue until 2,400 true guest frames or a typed, bounded failure. Persist reusable, compatible compiled artifacts in the established artifact store.

**Success is not merely one shell command executing multiple fresh applications invisibly.** Silent restart-and-input-replay, a stationary/fake frame count, neutral-only run followed by live preview, and an always-on viewer with a game subprocess being destroyed all fail the requested same-session acceptance requirement.

This is a major native architectural deliverable. Do not promise that an arbitrary unseen commercial ROM can be made 2,400-frame/gameplay-correct within this single release before actual Windows owner acceptance. If a required capability remains unimplemented or real-ROM acceptance fails, deliver only a clearly marked **blocked candidate** with specific test failures and a bounded next engineering step; never claim completion by reducing the requested target.

## 3. Proposed native architecture and interfaces

1. **Controller-owned autonomous session** (`RecompDev.exe`): a new explicit `run --rom ... --auto-native --target-frames 2400 --video window --monitor window --input live` mode (illustrative, **not a current CLI**). The compiled controller owns session lifetime, work scheduling, source/tool provenance, recovery bounds, guest-frame accounting, monitor-event transport and error reporting. No game, CPU, or console branches in the controller. Existing `run`, `resume`, `preview`, `cache`, installer, and headless modes remain compatible.
2. **Guest execution context** (new size/version-checked C ABI): opaque CPU state + machine state + bus/mapping epoch + input/timing state, with snapshot/restore or state-in-place handoff at *safe instruction/block boundaries*. Defined authoritative checkpoint includes registers, flags, interrupt/IME state, halted state, stack, RAM, mapper, pending VDP/PSG/IRQ/DMA/device state, input state and guest timing *as applicable to each CPU/machine plugin*. No assumption that `RD_CpuState` currently contains the full Z80 state. Checkpoint failures must stop safely, not reset and silently replay.
3. **Missing-block signal and dispatcher** (new versioned ABI): report logical and physical PC, source hash, CPU variant, bank/mapping identity, instruction hash, code epoch and diagnostic reason. Dispatcher can atomically register new compiled blocks while guest execution is suspended. It must never execute a block whose source bytes, mapping or CPU/translator/host assumptions fail checks.
4. **Loadable native translation module** (new versioned plugin ABI): analysis backend emits PIC/shared native blocks; controller validates hash-pinned manifest, exact CPU semantic contract, compiler target/ABI and machine-bus API compatibility, then activates via a controlled platform loader. Windows `LoadLibrary`/`GetProcAddress` details remain behind the host/plugin service, with equivalent portable interface elsewhere. No in-place overwrite of loaded DLLs; atomic activation and safe unload epochs; immutable content-addressed module files. A matching cache object may be reused; otherwise compile only the newly required coverage and link it to previously verified blocks. Prevent branch target/mapper aliasing.
5. **Persistent presentation and monitor**: existing `rd_runtime_host` owns a window across the session and continues pumping Win32 messages when guest execution is paused or compilation is underway. Existing `RecompDevMonitor.exe` remains a separate controller-event subscriber, never directly reading a CPU/machine plugin. Publish `ANALYSING`, `COMPILING`, `RUNNING`, `PAUSED_UNTRANSLATED`, `ACTIVATING`, `RESUMED`, `BLOCKED` and completed states with truthful source/PC/frame and percentage *only when measurable*. No fabricated UI screenshots.
6. **Reusable semantics across systems**: the CPU plugin owns versioned opcode semantics, per-CPU variant and cycle/flag behavior; machine plugin owns bus, memory mapping, devices and IRQ handling; generic translator/backend consumes a portable semantic contract. The first runtime adapter may be Z80 + SMS, but no new game-specific code and no Z80 logic in the generic controller. Provide at least one different synthetic machine/CPU plugin fixture to prove decoupling. Do not claim Mega Drive, MIPS or PlayStation support until dedicated plugins exist and pass tests.
7. **Compatibility analyzer**: existing Python provider/Ghidra/Rizin may be invoked *as a tool by the native controller* initially. No new Python/PowerShell production scheduler. Native executable and DLLs own orchestration/session control, module validation/activation and monitor events. Preserve all v26 source-attested input/preview and history artifacts as separate safety and regression capabilities.

## 4. Anticipated component/file changes (to be finalised in implementation review)

| Component / current version | Proposed version | Source areas | Scope |
|---|---|---|---|
| Compiled controller `0.4.22` | `0.4.23` | `controller/main.cpp`, `native_job.cpp`, new `native_session.*`, controller ABI/test files | Opt-in single-call session scheduler, typed events, safe recovery limits, no game rules |
| Runtime host `0.1.1` | `0.2.0` | `runtime_host/include/rd_runtime_host.h`, `src/host.cpp` | Persistent window/pump and thread-affinity; add ABI by extension, never silently break v1 |
| Native machine runtime `0.1.1` | `0.2.0` | `runtime_sms/` + generic machine-state interface | SMS checkpoint adapter; generic checkpoint contract independent of SMS |
| Native translation `0.3.0` | `0.4.0` | `translation_pcode/`, `harness/`, new `rd_native_block_v1.h` | Bounded loadable code modules and dynamic dispatch by qualified source/context |
| Artifact store `0.1.1` | `0.2.0` | `controller/artifact_store.*`, `artifact_store_abi.*` | Immutable compiled module retention keyed by source/CPU/machine/ABI/compiler identities |
| Execution monitor `0.4.4` | `0.5.0` | `execution_monitor/native/`, diagnostics schemas/tests | Stable session and recovery lifecycle events, viewer remains open |
| CPU Z80 plugin `0.5.1` | `0.5.2` if required | `harness/plugins/cpu_z80.cpp`, `rd_plugin.h` | Complete safely serialisable runtime state adapter; no duplicated Z80 semantic code |
| Analysis compatibility `0.3.6` | `0.3.7` if needed | `analysis_integration/cli.py`, recovery provider | Emits source-attested native module artifact instead of only standalone EXE |
| Workspace/documentation `v0.4.9.26` | `v0.4.9.27` | `workspace/components.json`, `RELEASE_ID.txt`, release/prebuild/handover/changelogs/test registry | Version and evidence governance |

The **precise** ABI additions must be presented and validated before implementation: v1 extension with struct-size/version validation or a separate v2 entrypoint. Do not change the layout or meaning of an existing C ABI in place. The video SMS Mode 4 renderer is a separate issue; scrolling fidelity is not silently counted as repaired in this build.

## 5. Workflow and stop semantics

`NEW_ROM → SOURCE_ATTEST → ANALYSIS → MODULE_COMPILE → LOAD → OPEN_WINDOWS/RUN → UNKNOWN_BLOCK → PAUSE/SNAPSHOT → SOURCE_ATTEST/COMPILE → SAFE_MODULE_ACTIVATION → RESUME_SAME_STATE → 2400_FRAMES`.

For better visibility, the monitor/window should appear before long-running recovery whenever the native host can be initialized safely, and present last valid frame with `ANALYSING/COMPILING` during pauses. The frame counter counts **guest** frames, not UI refreshes. Snapshot/checkpoint must be verifiably identical across an inject-and-resume boundary; every pause has a bounded deadline and cancellation path. Input transitions occurring while paused must be queued or rejected via an explicit policy and their guest-cycle timestamps retained. No input replay is used to impersonate same-session resume. A recoverable failure is not turned into an infinite translation loop: guard on frontier repeat, lack of genuine coverage, time, memory, rounds and output bytes with machine-readable diagnostics.

## 6. Mandatory acceptance gates — falsifiable

**Native ABI and execution:**
- A synthetic CPU+machine pair runs the same native session across at least two forced missing-block boundaries; guest CPU/guest RAM/banking/device/checkpoint/input state matches a trusted uninterrupted reference at each resume. The **same** host/window identity survives module compilations and activations; no game process is restarted.
- Inject a new binary module after the runtime has started; verify the old module remains immutable, the correct newly compiled block is invoked by hash/physical mapping, no stale function pointer survives an unload, and invalid source/mapper/CPU version/ABI/compiler identities are rejected *before execution*.
- A separate synthetic machine implementation uses the same semantic/translation contract. A deliberately incompatible CPU variant is rejected. No ROM name/hash/address special case is present in production code.
- Power interruption, compiler failure, corrupt module, repeated stop, cache poisoning, cancellation, timeout and no-progress cases fail with explicit status; old source and active binaries remain unchanged.

**One-call acceptance with real ROMs on owner Windows:**
- On a clean source-matched ROM-specific cache, one invocation starts the two **real** RecompDev windows and compiles/recompiles without user-supplied job/resume commands. At least one independent, previously unseen SMS ROM is required. Record the literal command and ROM SHA.
- Where a missing-code stop occurs, the **same** guest process/state and windows continue, verified by session/process identity, checkpoint hashes before/after activation, PC/mapping/input timeline, and uninterrupted guest-frame counter; no fresh native app executable startup hides behind a single CLI call.
- Reach **2,400 genuine guest frames** with live input, or report explicit **BLOCKED acceptance**. Confirm nontrivial game-state and frame transitions; a repeated static image, a neutral-only exercise, or a frame-budget counter is insufficient evidence of playable visual correctness.
- Repeat on an existing tested ROM (Shinobi) as a regression, without title-specific patches. Do not claim independent CPU/VDP/PSG/audio/gameplay parity until separately checked against trusted references.
- Verify the second run discovers safe compiled modules by hash and reuses them without unnecessary recompilation. Mismatched CPU version, machine ABI or ROM mapping must invalidate reuse; Z80 semantics are shared, game-specific compiled coverage is not reused blindly.

**Release and documentation:**
- Maintain historical originals 642/642, versioned source IDs, Ghidra/Rizin/source provenance and all existing v26 regression suites; run native CMake + all CTest locally and then `ctest -C Release` with full Windows validation by the owner. Record counts and real DLL hashes.
- *Before a Windows build*, validate manifest fields and optional null/omission compatibility against the **actual** permanent installer and execute a producer-consumer fixture test for diagnostic ZIPs and recovery receipts; avoid v26's two preventable late integration failures.
- Package cumulative source deltas from the **actual committed baseline** after reading the owner's Git status; do **not** assume a v26 candidate was installed. Use only the permanent hash-pinned `Install-RecompDev-Release.ps1` and an immutable ZIP. `-Mode Validate` must not mutate installed source/runtime or original evidence. Promotion eligibility and track must be explicit; no runtime activation without independent owner acceptance.

## 7. Preserved results and rollback

Retain Shinobi's known source-attested recovery history (including the 2,400-frame replay and separate 2,400-frame live-input observation), Fantasy Zone's 76-frame translated-code gap, all current diagnostics/monitor recordings, existing 642 historical files, native CPU/machine plugins, P-code provider and artifact-store objects. New evidence stays in the owner's existing `C:\Projects\RecompDev-Evidence` subtree, cache in existing `C:\Projects\RecompDev-Artifacts\store\v1` unless a separately versioned migration is approved, and build transactions under the existing `C:\Projects\RecompDev-Build`. No in-place editing of historical objects. Existing CLI and native application path remains available for regression/rollback; installed source and runtime stay unchanged during validation.

## 8. Scope exclusions and honest completion rule

- No game-specific fix, opcode table cloned into machine plugins, retrofitted emulator/interpreter used as unacknowledged native recompiler, or cross-console support claim.
- No promise that every unknown ROM is valid or compatible, no silent emulator fallback when instruction semantics or mapping are uncertain. Missing device support blocks safely with evidence.
- No claim that 2,400 frames equals independent gameplay parity, correct scrolling, graphics or sound; the SMS VDP scrolling issue remains separately tracked.
- If seamless in-process checkpoint/activation cannot pass the acceptance gate, **do not substitute automatic relaunch/replay and call the milestone delivered**. Report exactly which native subsystem is incomplete, and preserve earlier working behavior.

## 9. Requested owner decision

**Owner approved 2026-11-08:** implement this v0.4.9.27 native milestone with the exact no-hacks architecture and fail-closed acceptance above. The first deliverable should be an independently testable **source-only candidate**, not an unapproved runtime install. Its readiness is determined by tests and evidence, not by a calendar date or an unconditional promise of one-build success.

**Approval reply:** `Approve PREBUILD-v0.4.9.27 Persistent Autonomous Native Execution.`
