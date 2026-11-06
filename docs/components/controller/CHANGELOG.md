# controller — independent changelog

## [0.4.6] - 2026-11-06

- **Changed:** Shared compiled native game runner moved into controller; executes preserved P-code game DLL with strict full-source identity and no Python execution for native-execute. Existing prepare/recover remain transitional.
- **Validation:** Linux C++ compilation and compiled native controller/P-code and generic banked-flow regression, along with existing workspace tests. Full Windows owner validation, real-ROM translation and semantic parity are not yet demonstrated.
- **Compatibility:** C plugin descriptor ABI and existing runtime bus ABI remain unchanged. New optional symbol extensions are loaded by the compiled controller; original history is untouched and all missing/ambiguous execution cases fail closed.

## [0.4.5] - 2026-11-05

- **Changed:** Native C++ `--stage discover` plugin loading and report generation; legacy discovery available via an explicit compatibility stage.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** Changed native controller and added a strict, versioned format discovery ABI; existing Python prepare/recover workflow remains transitional.

This file records only changes to `controller`. Component versioning is independent of workspace release tags.

## [0.4.4] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `controller` controller at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `v042_compiled_controller_version; v042_compiled_controller_registry; v042_compiled_controller_e2e`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `production-entrypoint`. Not a replacement for individual native recovery services; changing controller governance code does not imply a new compiled EXE.
