# RecompDev v0.4.9.8 — approved process-only amendment to v0.4.9.7 native candidate

**Status:** Requested by owner 2026-11-05. **Source baseline:** installed `workspace/v0.4.9.6`, Git `7243e62851684477764117398b48ee335673eac2`. **v0.4.9.7 has not been installed or tagged on owner's PC.**

## Owner-directed change and approval

The owner explicitly requested v0.4.9.7 be rebuilt **as a new version** using one Git-managed permanent PowerShell release installer under the project root, with a separate ZIP containing changed source files, an independent one-line invocation, protected Git commits/tags, native compilation and full tests. This authorises the **release-process change**, not the removal of any previously approved native-functionality gate.

The full v0.4.9.7 pre-build specification, explicitly approved beforehand, remains at [PREBUILD-v0.4.9.7.md](PREBUILD-v0.4.9.7.md). The native-controller and format-DLL implementation from that uninstalled candidate is incorporated without making game-specific runtime edits.

## Exactly what changes in this amendment

- Add project-root `Install-RecompDev-Release.ps1` protocol v1, stored in Git upon **accepted promotion**, not regenerated per release.
- Define `recompdev-source-release-v1` manifest and package SHA-256 outside the ZIP. Future releases ship only source-update ZIPs and reuse the same installed installer.
- First-time bootstrap: execute the separately supplied matching installer from Downloads **without copying files into the checkout**. Its SHA-256 must match the corresponding ZIP member; after a successful promoted release the script is checked into the project root and is used for subsequent releases.
- Verify clean expected Git HEAD and tag, original committed Git blob hashes, full file bytes, immutable original sources and protected paths; build/test in external staging before touching the checkout.
- Candidate `Validate` does not commit, tag or activate binaries. `Install` is allowed only for packages whose promotion eligibility is explicitly true and whose acceptance tests pass; create Git commit/tag/bundle and versioned runtime activation with rollback protection.
- Document the same process in README, development contract, handover, release-process manual and component-specific changelogs, and test its packaging policy.

## Binary scope

Inherited, still uninstalled: compiled controller 0.4.4 -> 0.4.5; `rd_cpu_z80` 0.2.0 -> 0.3.0; `rd_machine_sms` 0.1.0 -> 0.2.0; new `rd_format_sms`, `rd_format_md`, `rd_format_ps1` 0.1.0. The permanent installer is **release infrastructure**, not another CPU/hardware runtime. No other native plugin-version change is authorised in this amendment.

## Mandatory acceptance and blockers

- Windows build of the above EXE/DLLs, full 45 CTests, docs and Python suites, 642 original-file preservation, and source/active-binary hashes.
- Real Master System ROM -> newly source-verified discovery block -> full historical Ghidra P-code backend -> compiled native C++ acceptance remains **BLOCKED**. This is deliberately not misreported as complete. It requires real owner-side evidence; a synthesized toy translator or title-specific patch is not acceptable.
- Shinobi parity and reversed scrolling around frame 730/stop `0x4F9E` remain unresolved; monitor and deterministic recovery evidence are mandatory continuity checks.
- Package is therefore **CANDIDATE ONLY** with `promotion_eligible=false`. It must not be tagged `workspace/v0.4.9.8` or alter active DLLs until the outstanding mandatory gate is fulfilled and Windows acceptance is recorded.

## Explicit exclusions

No rewrite of the native-game translator, no changes to historical `legacy/`/`baselines/`, no commercial ROMs in the ZIP, no forced retirement of existing Python/Ghidra tools, and no new installer per release. Do not mark Linux-only testing as Windows acceptance. The standard installer is to remain stable and independently versioned.

## 2026-11-06 — owner-directed installation scope amendment (after Windows validation)

The user confirmed that **v0.4.9.7 was never installed**, then validated v0.4.9.8 source and native discovery under Windows: docs PASS, Python 21/21 + 10/10 + 6/6, all 642 original historical files identical, MSVC build PASS, CTest **45/45 PASS**. With no Git commit/tag or activated binaries after `-Mode Validate`, the owner explicitly requested an **installable ZIP before any more development**.

**Revised acceptance contract for the v0.4.9.8 installation (approved by that explicit request):** preserve native discovery versions and source from the validated candidate; rerun the full mandatory test suite in `-Mode Install`; commit a clean Git checkout, create `workspace/v0.4.9.8` tag, verify Git bundle, activate versioned EXE/DLLs and update the lockfile with SHA-256, or restore the previous state. Controller lockfile entry is named `controller` rather than by executable basename. Report installation failure honestly. No additional native instruction semantics or games are claimed.

**Deferred rather than discarded:** real Master System ROM block discovery through full preserved Ghidra P-code translation into a native compiled game is **not** a v0.4.9.8 installation acceptance criterion. It remains the first development milestone after this installed release, under the same approved modular-native architectural contract. This scope reduction is specifically to complete the requested native discovery/release installation without continuing indefinite validation-only candidates. No change to Shinobi code, historical 642 files, or original v0.4.9.7 approved report.

**Risk:** the `Install` path (not just `Validate`) has not yet run on the owner's Windows machine; this first run is its necessary operational qualification. All expected preflight checks run before source overwrite. Rollback is required on any post-mutation failure.
