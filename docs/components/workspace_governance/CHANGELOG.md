# workspace_governance — independent changelog

This file records only changes to `workspace_governance`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Introduced the `workspace_governance` tooling component in the v0.4.5 workspace snapshot, with release-documentation checks, component changelog validation and a transactionally applied source-only update path.
- **Validation:** Baseline or target tests: `workspace.tests.test_docs_governance; v044_workspace_contract`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `workspace`. Changes release tooling only; no native binary is installed or rebuilt.
