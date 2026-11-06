# release_installer — permanent source-release transaction

**Component:** `release_installer` 1.0.0. **Scope:** `workspace`. Independent registration: `workspace/components.json`.

`Install-RecompDev-Release.ps1` lives in the Git-managed root and is the **single permanent PowerShell installer**, not a game runtime or another Python controller. Every release uses the same file with `-Package`, `-ExpectedSha256` and optional `-Mode Validate|Install` parameters.

It verifies the independently supplied ZIP SHA-256 before extraction, checks manifest-listed file paths and source hashes against canonical Git blobs, rejects changes to `legacy/` and `baselines/`, stages changes outside Git, builds CMake native targets, runs `ctest -C Release` and Python/source-preservation checks, and produces external evidence.

`Validate` never modifies the source, creates a Git tag or deploys binaries. `Install` is available only when the ZIP declares **promotion eligible** and mandatory tests succeed. Git commit, tag and backup bundle are part of a rollback-protected transaction. Installed DLLs follow versioned runtime storage and active binary hashes.

**First-time bootstrap:** a not-yet-installed checkout has no root installer. Execute the matching separately supplied `Install-RecompDev-Release.ps1` from Downloads exactly once, pinning the package SHA-256 via the command. A successfully promoted release includes and commits this exact script to the root; later releases use the root copy. Merely validating an unfinished candidate cannot install the bootstrap script or make a tag.

No commercial ROMs, compilation outputs or evidence databases are included in release ZIPs. Windows PowerShell 5.1 remains a required acceptance target. See [release-process standard](../../development/RELEASE-PROCESS.md) and [development contract](../../project/DEVELOPMENT-CONTRACT.md).
