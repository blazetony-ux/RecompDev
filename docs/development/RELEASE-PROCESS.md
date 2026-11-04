# Git release process and documentation gates

**Status:** Current for v0.4.5 governance tooling. Last reviewed: 2026-11-04.

## Component releases versus workspace snapshots

Each component owns its version and `docs/components/<id>/CHANGELOG.md`. Increment **only the component whose implementation or contract changes**. A workspace tag `workspace/vA.B.C` records a validated combination of components and documentation; it does not force changing any DLL or controller version. Immutable binary hashes are enforced by the runtime store.

## Acceptance checks (automated)

1. Allow only the named component source boundary, its `workspace/components.json` version increase and its own changelog file. Never stage unrelated untracked files or secrets.
2. Require `## [new.version] - YYYY-MM-DD` in the **changed** component changelog, followed by meaningful `Changed`, `Validation`, and `Compatibility` information. Generic words such as 'updated plugin' are insufficient.
3. Compile only the selected CMake target; run relevant regression gates and unchanged historical-source preservation checks.
4. Git-commit approved source and docs together **only after** those checks succeed; then activate the independently versioned binary, retaining the previous binary for rollback.
5. A workspace release also checks [documentation standards](DOCUMENTATION-STANDARDS.md), the release note `docs/releases/vA.B.C.md`, matching `CHANGELOG.md`, a clean working tree and the full existing CTest suite. Create tag and external Git bundle only afterward.

The documentation gate is implemented in `workspace/docs_governance.py`, called by `workspace/manager.py`. The existing compiled controller forwards these new source-only commands without a rebuild:

```powershell
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin docs-check
& 'C:\Projects\RecompDev-Runtime\RecompDev.exe' plugin docs-accept
```

`docs-check` validates the knowledge base without compiling; `docs-accept` Git-commits a **documentation-only** change after tests, with no component version bump. When governance tooling code itself changes, bump and accept only `workspace_governance`; its acceptance runs Python/documentation tests without building a C++ DLL.

## Documentation-only releases

A documentation-only workspace update is allowed. It updates **only** docs and the separately versioned `workspace_governance` tooling if necessary, tests those tools and existing binaries, commits the approved changes and tags the workspace. It does **not** redeploy or increment the controller, CPU or hardware DLL versions. The v0.4.5 migration includes a single-file source update that checks original hashes, takes an external backup, validates, and restores files if a pre-commit step fails.

## Failure states and rollback

If a targeted build/test/docs gate fails, no new binary should be activated and no release tag created. Source edits from manual development remain visible for correction; packaged updates should restore their old source files. A commit that passes tests but fails activation is explicit `COMMITTED_NOT_ACTIVATED`, never a false success. A Git revert/checkout is distinct from runtime plugin rollback.

## Evidence and release metadata

Keep human-readable notes in `docs/releases/` and relevant component changelogs. Build/test logs and upload ZIPs go to external `RecompDev-Evidence` roots. A release note must say *what was actually tested*, on which platform, and which limitations remain. Historical snapshots are not retroactively rewritten as proven gameplay parity.
