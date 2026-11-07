# rd_machine_sms — independent changelog

## [0.4.0] - 2026-11-07

- **Changed:** The SMS machine plugin now compiles against maintained runtime state headers and links the independent `rd_sms_native_runtime` and `rd_video_sms_mode4` DLLs instead of compiling frozen Master System runtime sources. All existing bus/mapper descriptors and external CPU-discovery extensions remain in place.
- **Validation:** Full available Linux harness regression and an independent C++ source-attested bank-6 runtime/Mode-4/frame-host smoke execute without static linkage to the historical runtime. Actual graphical pixel parity, deterministic controls and Windows dynamic loading are still acceptance gates.
- **Deployment:** Requires new `rd_sms_native_runtime` alongside existing Mode-4 renderer in the active plugin store; the controller uses DLL-load-directory search flags to resolve these dependent modules from their actual location.
- **Compatibility:** Prior machine descriptor and source mapper C ABIs are unchanged. New DLL dependency must be present alongside the machine plugin at deployment; historical reference files remain byte-identical.

## [0.3.0] - 2026-11-06

- **Changed:** Original SMS initial mapper and register-write effects now model context-qualified ROM physical offsets, retaining existing bus and source resolver compatibility.
- **Validation:** Linux C++ compilation and compiled native controller/P-code and generic banked-flow regression, along with existing workspace tests. Full Windows owner validation, real-ROM translation and semantic parity are not yet demonstrated.
- **Compatibility:** C plugin descriptor ABI and existing runtime bus ABI remain unchanged. New optional symbol extensions are loaded by the compiled controller; original history is untouched and all missing/ambiguous execution cases fail closed.

## [0.2.0] - 2026-11-05

- **Changed:** Conservative static-ROM reset/interrupt source mapping with dynamic/banked addresses remaining unresolved.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** New `rd_sms_resolve_source_v1` extension; runtime bus ABI remains unchanged.

This file records only changes to `rd_machine_sms`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `rd_machine_sms` compiled-plugin at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `hybrid_bank2_parity; hybrid_input_parity`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `harness`. No independently validated video/PSG/IRQ gameplay parity; production engine has separate implementation.
