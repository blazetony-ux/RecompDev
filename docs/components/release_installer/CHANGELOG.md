# release_installer — component changelog

## [1.0.0] - 2026-11-05

- **Changed:** Introduced a permanent root-level Git-managed PowerShell installer that consumes independently SHA-256-pinned source ZIPs with a versioned manifest, extracts to external staging and verifies canonical committed Git blobs instead of checkout- or archive-dependent line endings. Separate validation and promotion modes, with protected history paths.
- **Validation:** Source package integrity, manifest path and hash cross-checks, synthetic incorrect-baseline/mutation rejection, Linux release-protocol tests, documentation governance and existing CMake/C++ regressions. Windows end-to-end PowerShell 5.1 execution remains a mandatory outstanding acceptance before any promotion.
- **Compatibility:** New release infrastructure only. No existing v0.4.9.6 executable, native-game project, CPU plugin or Shinobi runtime is touched by candidate validation; previous standalone installers remain archived but are not the future release interface.

## [1.0.0 installable promotion amendment] — 2026-11-06

- Align the compiled controller's active lockfile identity with existing `controller` instead of executable basename `RecompDev` so subsequent component operations continue to resolve the real active binary.
- Restore Git index on a failed release commit; verify final Git HEAD, tag, clean worktree, runtime lockfile and activated hashes before printing INSTALLED.
- Use the same permanent source-embedded installer for an owner-approved, installable native-discovery-scoped v0.4.9.8 ZIP. The real-ROM-to-P-code game build is deferred transparently.
