## v0.4.9.16 — single-ZIP development checkpoint

`release_installer` 1.1.0 supports one SHA-256-pinned release ZIP with a package-internal installer. `Validate` now creates a `dev` checkpoint using an isolated Git index **only after** full tests, preserving the clean main checkout and active binaries. Use the package-pinned installer to enable the new feature while main still contains the v0.4.9.9 root installer. Windows PowerShell gate pending; no auto-push to GitHub. See [release](../../releases/v0.4.9.16.md).

# release_installer — permanent source-release transaction

**Component:** `release_installer` 1.0.0. **Scope:** `workspace`. Independent registration: `workspace/components.json`.

`Install-RecompDev-Release.ps1` lives in the Git-managed root and is the **single permanent PowerShell installer**, not a game runtime or another Python controller. Every release uses the same file with `-Package`, `-ExpectedSha256` and optional `-Mode Validate|Install` parameters.

It verifies the independently supplied ZIP SHA-256 before extraction, checks manifest-listed file paths and source hashes against canonical Git blobs, rejects changes to `legacy/` and `baselines/`, stages changes outside Git, builds CMake native targets, runs `ctest -C Release` and Python/source-preservation checks, and produces external evidence.

`Validate` never modifies the source, creates a Git tag or deploys binaries. `Install` is available only when the ZIP declares **promotion eligible** and mandatory tests succeed. Git commit, tag and backup bundle are part of a rollback-protected transaction. Installed DLLs follow versioned runtime storage and active binary hashes.

**First-time bootstrap:** a not-yet-installed checkout has no root installer. Execute the matching separately supplied `Install-RecompDev-Release.ps1` from Downloads exactly once, pinning the package SHA-256 via the command. A successfully promoted release includes and commits this exact script to the root; later releases use the root copy. Merely validating an unfinished candidate cannot install the bootstrap script or make a tag.

No commercial ROMs, compilation outputs or evidence databases are included in release ZIPs. Windows PowerShell 5.1 remains a required acceptance target. See [release-process standard](../../development/RELEASE-PROCESS.md) and [development contract](../../project/DEVELOPMENT-CONTRACT.md).

## Source-only infrastructure promotion

From workspace v0.4.9.17, manifest `release_track=infrastructure-source` with `promotion_scope=git-main-only-no-runtime` can update Git main and tag after full testing through the permanent Git-managed installer `-Mode Install`. The active compiled controller binary, plugin DLLs and runtime lockfile remain untouched. Full native-game qualification remains a separate acceptance track.

## v0.4.9.18 main-parent checkpoint

A source-only package may declare `development_checkpoint.parent_branch=main` only when the checked out `main` commit exactly equals the package baseline and its expected `workspace/v0.4.9.17` tag. `-Mode Validate` can create a versioned dev checkpoint with an isolated index; `-Mode Install` independently revalidates and promotes source-only, leaving active runtime binaries alone. This prevents demanding a nonexistent `dev/v0.4.9.17` branch after the owner's prior direct main promotion.
