# RecompDev — permanent Git-managed release process (protocol v1)

**Effective design:** v0.4.9.8 installable native-discovery release; owner Install-mode result pending. **Validated local owner baseline:** workspace/v0.4.9.6 (`7243e62851684477764117398b48ee335673eac2`). The v0.4.9.7 candidate was **never installed**.

## One permanent script, one source ZIP per future build

The sole source release entry point is `C:\Projects\RecompDev\Install-RecompDev-Release.ps1`, versioned as `release_installer` in `workspace/components.json`, with [component documentation](../components/release_installer/README.md). Do not issue new `Apply-...ps1` or `Validate-...ps1` installers per release. Existing named scripts remain historical reference and are not the future distribution method. One optional game-launch wrapper may remain.

Each new package is named `RecompDev-vX.Y.Z.zip` and contains only `release-manifest.json` plus `files/<source-relative-path>` for every changed file. The manifest pins expected Git HEAD and baseline release tag, old/new per-file SHA-256, changed native binary targets/versions, commit message, promotion status and mandatory test names. It does **not** contain commercial game files, external catalogues, binaries, `legacy/` or `baselines/` modifications.

A user-visible one-line command must provide an **independent SHA-256 of the complete ZIP** via `-ExpectedSha256`; the installer must verify that value before trusting the manifest or extracting anything. Hashes *inside* a ZIP alone are insufficient to authenticate its provenance.

## One-time bootstrap only (v0.4.9.8)

The installed v0.4.9.6 has no Git-managed root installer. On the first attempt only, download the permanent installer alongside the ZIP and execute **the matching Downloads copy** in `Install` mode (after the full Windows Validate-mode pass):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\Install-RecompDev-Release.ps1" -Package "$env:USERPROFILE\Downloads\RecompDev-v0.4.9.8.zip" -ExpectedSha256 "<independently-provided-64-hex-zip-hash>" -Mode Install
```

The independent ZIP SHA-256 and a byte-for-byte match between the downloaded bootstrap and the ZIP-embedded script are checked first. In `-Mode Install`, only a successful end-to-end transaction copies the source into the Git checkout, commits the permanent installer, creates the tag and activates the binaries. Failure before or after that point must not be called installed. `-Mode Validate` never changes source, Git tags or active binaries.

## Standard command after the root installer is Git-managed

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\RecompDev\Install-RecompDev-Release.ps1" -Package "$env:USERPROFILE\Downloads\RecompDev-vX.Y.Z.zip" -ExpectedSha256 "<independently-provided-64-hex-zip-hash>" -Mode Install
```

`-ExecutionPolicy Bypass` changes only that PowerShell process; it is not antivirus, application-control or organisational policy bypass. Do not modify machine-wide policy.

## Transaction and safety requirements

1. Verify independent package SHA-256, safe nonduplicated ZIP paths, manifest file hashes and source content. Refuse protected historical paths and unexpected binary files.
2. Verify clean Git checkout and **exact baseline commit**. Match old SHA-256 against raw `git cat-file blob HEAD:path` bytes, not line-ending-dependent worktree copies or ZIP extraction. Verify tag matches HEAD.
3. Stage Git archive and changed source outside the checkout; run docs governance, affected Python tests, original 642-file preservation, full CMake build and `ctest --test-dir ... -C Release` in external paths. Record actual built EXE/DLL hashes.
4. `-Mode Validate` stops without modifying Git source, tags, active DLLs or original ROMs. A candidate with unmet approved requirements stays **BLOCKED** even if tests pass.
5. `-Mode Install` is permitted only for a promotion-eligible manifest and successful mandatory acceptance. Apply exactly the manifest-declared files; Git add/commit/tag; create/verify external Git bundle; activate versioned EXE/DLL binaries with SHA-256 lockfile; preserve previous active binaries for rollback. No failed release may be reported `INSTALLED`.
6. Report actual build/test results, source and compiled version changes, bundle location and rollback status. Do not conceal missing Windows tests or claim native gameplay parity.

The installer must remain stable across releases and be changed only through a separately approved, versioned, regression-tested amendment. Native discovery, translation, runtime and monitoring remain responsibilities of `RecompDev.exe` and DLL plugins, **not** an expanding collection of PowerShell/Python wrappers.

## v0.4.9.8 first owner installation

Owner Windows 2026-11-06 `Validate` passed 45/45 CTests, docs, Python tests, and 642 original-file hashes, but left Git at v0.4.9.6 by design. The owner subsequently approved promoting the implemented discovery-only scope as an installable release. The previously approved real-ROM P-code-to-native-build demonstration remains an explicit follow-up engineering milestone. The v0.4.9.8 installable package uses `promotion_eligible=true`, requires named existing acceptance tests and reruns the full suites before touching the live checkout; it does not waive integrity or parity claims. The first actual `Install` run must be independently verified by checking `git log -1`, `git tag --points-at HEAD`, clean `git status`, and active component hashes.

## v0.4.9.17 independent infrastructure promotion

A source ZIP may be explicitly labelled `release_track=infrastructure-source` and `promotion_scope=git-main-only-no-runtime`. Under the single Git-managed permanent `Install-RecompDev-Release.ps1`, `-Mode Validate` performs the full tests and creates only `dev/v0.4.9.17`; `-Mode Install` requires a fresh full verification and then updates Git source `main`/tag with a local Git backup while leaving active runtime binaries and `active-components.json` untouched. No automatic GitHub push. Do not set gameplay qualified or silently waive the 1,800-frame deliverable. The runtime activation track is separately blocked until independently qualified. Always record current `main` and runtime state from the actual owner output.

## v0.4.9.18 current-main source checkpoint rule

After v0.4.9.17 was promoted directly to Git `main` and published to GitHub (without a `dev/v0.4.9.17` branch), `Validate` may create the next dev checkpoint with `development_checkpoint.parent_branch=main` only when `parent_commit` matches the manifest's exact `baseline_commit` and the installer has already verified that same HEAD and release tag. This is exclusively for the `infrastructure-source` track. The source-only runtime-immunity gate, rollback and full Windows acceptance remain unchanged. `Install` promotes Git source locally only and does not push to GitHub.
