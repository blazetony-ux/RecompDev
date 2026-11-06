# controller — independent changelog

## [0.4.5] - 2026-11-05

- **Changed:** Native C++ `--stage discover` plugin loading and report generation; legacy discovery available via an explicit compatibility stage.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** Changed native controller and added a strict, versioned format discovery ABI; existing Python prepare/recover workflow remains transitional.

This file records only changes to `controller`. Component versioning is independent of workspace release tags.

## [0.4.4] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `controller` controller at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `v042_compiled_controller_version; v042_compiled_controller_registry; v042_compiled_controller_e2e`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `production-entrypoint`. Not a replacement for individual native recovery services; changing controller governance code does not imply a new compiled EXE.
