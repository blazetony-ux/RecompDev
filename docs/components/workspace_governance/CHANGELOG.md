# workspace_governance — independent changelog

This file records only changes to `workspace_governance`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Introduced the `workspace_governance` tooling component in the v0.4.5 workspace snapshot, with release-documentation checks, component changelog validation and a transactionally applied source-only update path.
- **Validation:** Baseline or target tests: `workspace.tests.test_docs_governance; v044_workspace_contract`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `workspace`. Changes release tooling only; no native binary is installed or rebuilt.

## [0.1.1] - 2026-11-04

- **Changed:** Added explicit source ownership boundaries for the production CPU admission bridge and Z80 ABI header, plus component-focused Python regression checks and restoration of the previously active DLL if activation cannot update its runtime lockfile.
- **Validation:** Preserved workspace manager and governance unit tests, new production CPU gate tests, full prebuilt CTest suite, source SHA-256 protection, and unchanged runtime binary checks for all unrelated components.
- **Compatibility:** Previous workspace operations and component versions are unaffected; special coordinated bridge migration is only required to establish the additional new component once. Future Z80 DLL updates remain independently buildable and releasable.
