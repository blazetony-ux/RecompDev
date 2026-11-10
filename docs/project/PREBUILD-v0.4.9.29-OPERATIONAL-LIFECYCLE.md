# v0.4.9.29 — Operational runtime and artifact lifecycle: implementation contract

**Baseline:** promoted `workspace/v0.4.9.28`, commit `724d190eeb0928ebab4e242e9aba4d2cef016505`. **Status:** owner-authorised source-only promotion; native runtime remains unqualified and unchanged. This release is the P0 roadmap milestone, not a documentation-only change. See [roadmap](ROADMAP.md), [development contract](DEVELOPMENT-CONTRACT.md), [original approved production prebuild](PREBUILD-v0.4.9.7.md) and [release record](../releases/v0.4.9.29.md).

## User outcomes

- Every verified new code discovery checkpoints reproducible native C++ locally before any optional network operation, and queues the current per-ROM Git commit for publication in the existing private `RecompDev-plugins/main` layout.
- When GitHub is unavailable, gameplay continues. A durable pending commit survives process exit and is automatically retried on the next launch even with **zero** new translations; periodic bounded retries occur during longer live sessions.
- An operator or release installer can query exact pending counts; `VERIFIED` is never emitted while pending commits remain. The existing original per-game Git commits, relative tree contents and checked-out newer local work are never overwritten.
- An installer verifies all compiled runtime binaries and stages a complete immutable candidate image **outside** the active runtime. No Windows active runtime is replaced without independent gameplay/parity approval and an explicitly reviewed rollback transaction.

## Component-level changes

| Component | Owner and concrete changes | Non-negotiable boundaries |
| --- | --- | --- |
| `analysis_integration/generated_source_sync.py` | Validated queue parser, `retry-pending`, bounded in-session retry with backoff, startup retry and terminal pending-state diagnostics | No ROM bytes/DLLs in Git; no force push; no machine-specific logic; no blocking gameplay |
| `analysis_integration/runtime_stage.py` | Stage/verify immutable SHA-256 image from verified Windows build inventory | NEVER activate or mutate production runtime/lockfile; reject changed binaries and duplicate versions |
| `analysis_integration/live_session.py` | Use new sync lifecycle and v29 session provenance | Keep existing native recovery, source checkpoint and input behaviour |
| `Install-RecompDev-Release.ps1` | After CTests create and verify external candidate runtime image; report pending count explicitly during post-install source restore and publish | Preserve original SHA-pinned package and Git rollback procedures; source-only promotion remains strict |
| `controller/main.cpp`, `workspace/components.json`, `harness/CMakeLists.txt` | Version metadata, component versions, three independent additional CTests | Preserve native plugin ABIs and existing 91 tests |
| Documentation | This contract, authoritative roadmap, candidate release notes, component changelogs and handover | No modifications to frozen historical trees |

## Acceptance checklist — testable, not aspirational

1. 94/94 Windows MSVC CTests + source governance + 642/642 historical integrity; versioned read-only release ZIP preflight (`-Mode Validate`).
2. Source sync: local new commit -> pending marker -> GitHub outage -> process exit -> next run with **no new instructions** -> automatic retry -> remote commit/tree match -> pending 0. Validate on disposable remotes and the owner's private GitHub (only after approval).
3. Reinstall: isolated empty `RECOMPDEV_HOME` restores exact Fantasy Zone/Shinobi histories (including most recent Shinobi commit) from one `main` without new per-game branches; new local unpushed source survives reinstall without clobber.
4. Runtime stage: all binaries from `native-binary-hashes.json` copied to a new immutable image; every SHA matches; a tampered DLL is rejected; active runtime remains byte-for-byte unchanged. **Actual active runtime cutover and rollback are not yet provided by this stage command and must not be claimed qualified.**
5. No regressions: real-game controller 2,400 frames and keyboard/scrolling remain a further acceptance check, audio/hardware parity remain explicitly unverified. The owner-requested source-only promotion may create the source Git tag; runtime cutover and gameplay qualification still require their own signoff.

## Delivery and rollback policy

- Deliver a complete source-delta ZIP with exact Git base tag/commit and old/new per-file SHA-256, all tests and documentation; owner-authorised source-only package uses `promotion_eligible=true`, `promotion_blocker=null`, `gameplay_qualified=false`, `infrastructure-source`, `git-main-only-no-runtime`. This is not acceptance of active runtime deployment or a claim that deferred owner-live tests have passed.
- Validation creates disposable CMake binaries and an isolated external staged-image artifact; it neither installs nor tags nor activates a production runtime.
- Failed GitHub publication leaves the exact local Git source and durable queue untouched. Re-running synchronization must be idempotent. If a new commit differs from an existing remote path, stop rather than overwrite silently.
- Remediation of failing native runtime activation or parity requires a separate candidate with explicit test evidence and owner approval; never relax the source-only installer guard.

**Owner Windows evidence (2026-11-10):** 94/94 CTests, 47/47 Python tests, 642 historical file hashes, dedicated 5/5 retry tests, idle retry with zero pending and five staged-binary SHA-256 matches. **Deferred, not passed:** real unattended private GitHub outage/restart publication; fresh-home Fantasy Zone/Shinobi restoration; actual 2,400-frame real-game/keyboard test; runtime cutover/rollback; standalone EXE export; independent audio/hardware parity. Source-only Git promotion is owner-authorised independently of these deferred runtime/product acceptance gates.
