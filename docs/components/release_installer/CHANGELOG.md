# release_installer — component changelog

## [1.3.0] - 2026-11-09

- **Changed:** Following verified local install, automatically restore per-ROM generated source from configured shared `main` checkout. An optional `-PublishOrigin` flag atomically pushes the canonical controller main and new release tag after the verified Git commit, annotated tag and rollback bundle.
- **Validation:** Local static contract and disposable Git tests exercise ordering and restore, with owner Windows PowerShell Validate/Install and remote publication still required; the protected 642 historical files are not modified.
- **Compatibility:** Infrastructure-source promotion continues to leave active executable and DLLs unchanged. Remote failure is reported pending and never triggers destructive Git force-push, source rollback or gameplay claims.


## [1.2.1] - 2026-11-07

- **Changed:** Source-only `Validate` checkpoints can use the exact, verified `main` baseline as parent when no `dev/v0.4.9.17` branch was created by an `Install`-only promotion. Reject this parent for gameplay/runtime release tracks or mismatched baseline hashes.
- **Validation:** Isolated-index checkpoint test and explicit-main-parent source policy; full Windows end-to-end test and Git main/tag/rollback still owner gates.
- **Compatibility:** One ZIP, unchanged production EXE/DLL/lockfile on source-only promotion; no GitHub push.


## [1.2.0] - 2026-11-07

- **Changed:** Explicit `infrastructure-source` release track with `git-main-only-no-runtime` promotion scope. After exact package hash, source preservation, governance and full named Windows CTests, `-Mode Install` may update source `main` and a Git tag while deliberately leaving active runtime EXE/DLLs and lockfile untouched. The Shinobi 1,800-frame qualification is retained for separately approved gameplay-runtime acceptance.
- **Validation:** Automated source-level separation tests reject accidental runtime copy or a missing release-track guard; the existing rollback, detached Git-backup and isolated `Validate` checkpoint tests remain. Windows PowerShell 5.1 Install transaction still requires owner validation and approval before calling it installed.
- **Compatibility:** Single SHA-pinned source ZIP and transactional rollback remain. No GitHub push, force operation, automatic runtime promotion or gameplay-success assertion is performed.

## [1.1.0] - 2026-11-07

- **Changed:** A single release ZIP embeds a SHA-256-pinned updated installer. On `Validate` after the complete source and compiled test suite passes, it can write a new versioned `dev` Git checkpoint from staged candidate files with an isolated index and worktree, without separate user-downloaded Git bundles. The expected prior `dev` commit is mandatory.
- **Validation:** Portable Git plumbing test verifies development ref content and unchanged checked-out main; source tests require full CTest preceding checkpoint creation and retained promotion guard. Windows PowerShell 5.1 end-to-end is pending.
- **Compatibility:** `Install` remains gated by `promotion_eligible=true`, source history safeguards and rollback. `Validate` never changes active source/main, production tags or runtime binaries, and never publishes to GitHub automatically.

## [1.0.0] - 2026-11-05

- **Changed:** Introduced a permanent root-level Git-managed PowerShell installer that consumes independently SHA-256-pinned source ZIPs with a versioned manifest, extracts to external staging and verifies canonical committed Git blobs instead of checkout- or archive-dependent line endings. Separate validation and promotion modes, with protected history paths.
- **Validation:** Source package integrity, manifest path and hash cross-checks, synthetic incorrect-baseline/mutation rejection, Linux release-protocol tests, documentation governance and existing CMake/C++ regressions. Windows end-to-end PowerShell 5.1 execution remains a mandatory outstanding acceptance before any promotion.
- **Compatibility:** New release infrastructure only. No existing v0.4.9.6 executable, native-game project, CPU plugin or Shinobi runtime is touched by candidate validation; previous standalone installers remain archived but are not the future release interface.

## [1.0.0 installable promotion amendment] — 2026-11-06

- Align the compiled controller's active lockfile identity with existing `controller` instead of executable basename `RecompDev` so subsequent component operations continue to resolve the real active binary.
- Restore Git index on a failed release commit; verify final Git HEAD, tag, clean worktree, runtime lockfile and activated hashes before printing INSTALLED.
- Use the same permanent source-embedded installer for an owner-approved, installable native-discovery-scoped v0.4.9.8 ZIP. The real-ROM-to-P-code game build is deferred transparently.
