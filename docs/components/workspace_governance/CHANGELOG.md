# workspace_governance — independent changelog

## [0.1.5] - 2026-11-05

- **Changed:** Mandate root release-installer presence and documented permanent ZIP protocol in workspace v0.4.9.8 and later; retain approved native-development contract and correct newest-first workspace changelog verification.
- **Validation:** Documentation-governance regression fixtures include the permanent installer; added missing-installer negative test and cross-release source-only validation with frozen-history protection.
- **Compatibility:** Release policy enforcement only, no running game modification, executable replacement or new CPU semantics. Existing v0.4.9.6 compiled runtime remains untouched by candidate validation.

## [0.1.4] - 2026-11-05

- **Changed:** Mandatory binding development contract, approved pre-build report and handover/release acknowledgement.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** New policy omissions automatically fail documentation governance; no ROM or binary modifications.

## [0.1.3] - 2026-11-05

- **Changed:** Enforce a single document title, unique workspace release headings and newest-first ordering; normalised the historical workspace changelog without editing prior release descriptions.
- **Validation:** New negative tests cover missing/misplaced title, out-of-order versions and duplicates, plus existing full documentation governance and regression checks.
- **Compatibility:** No compiled controller or runtime plugins change. Preserved historical sources and source-to-ROM validation remain unaffected.


## [0.1.2] - 2026-11-05

- **Changed:** Recognise optional fourth numeric segments in workspace patch-release tags (e.g. `workspace/v0.4.9.1`) without changing independently versioned component semantics, source preservation policy, or Git release requirements.
- **Validation:** Documentation validation tests for both three-part releases and patch release tags, enforced component changelog headings, verified links, and unchanged frozen source baselines.
- **Compatibility:** No compiled binaries, plugin ABI, active DLL versions, original source, ROM or owner catalogue changes. Existing release tags and three-part versions remain valid.
This file records only changes to `workspace_governance`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Introduced the `workspace_governance` tooling component in the v0.4.5 workspace snapshot, with release-documentation checks, component changelog validation and a transactionally applied source-only update path.
- **Validation:** Baseline or target tests: `workspace.tests.test_docs_governance; v044_workspace_contract`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `workspace`. Changes release tooling only; no native binary is installed or rebuilt.

## [0.1.1] - 2026-11-04

- **Changed:** Added explicit source ownership boundaries for the production CPU admission bridge and Z80 ABI header, plus component-focused Python regression checks and restoration of the previously active DLL if activation cannot update its runtime lockfile.
- **Validation:** Preserved workspace manager and governance unit tests, new production CPU gate tests, full prebuilt CTest suite, source SHA-256 protection, and unchanged runtime binary checks for all unrelated components.
- **Compatibility:** Previous workspace operations and component versions are unaffected; special coordinated bridge migration is only required to establish the additional new component once. Future Z80 DLL updates remain independently buildable and releasable.
