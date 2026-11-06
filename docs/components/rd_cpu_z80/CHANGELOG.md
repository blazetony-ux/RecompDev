# rd_cpu_z80 — independent changelog

## [0.4.0] - 2026-11-06

- **Changed:** Source-only Z80 length/control-flow decode expanded to documented ED/CB, DD/FD indexed forms; exports conservative A/SP and memory-write abstractions, while old synthetic fixture interpreter is unchanged.
- **Validation:** Linux C++ compilation and compiled native controller/P-code and generic banked-flow regression, along with existing workspace tests. Full Windows owner validation, real-ROM translation and semantic parity are not yet demonstrated.
- **Compatibility:** C plugin descriptor ABI and existing runtime bus ABI remain unchanged. New optional symbol extensions are loaded by the compiled controller; original history is untouched and all missing/ambiguous execution cases fail closed.

## [0.3.0] - 2026-11-05

- **Changed:** Conservative source-byte-verified Z80 decode, including explicit unsupported prefix and indirect control-flow gaps.
- **Validation:** Linux CMake/CTest native discovery contract and existing harness regressions; full Windows and real-ROM translation/build remain acceptance gates.
- **Compatibility:** New `rd_z80_decode_source_v1` extension, retaining original interpreter and production gate ABI.

This file records only changes to `rd_cpu_z80`. Component versioning is independent of workspace release tags.

## [0.1.0] - 2026-11-04

- **Changed:** Initial documented inventory for the existing `rd_cpu_z80` compiled-plugin at the v0.4.4 migration baseline; existing source and deployed binaries unchanged by the documentation migration.
- **Validation:** Baseline or target tests: `unsupported_opcode_rejected; hybrid_main_parity; native_only_single_block`; do not interpret these as real-game parity claims.
- **Compatibility:** Scope is `harness`. Not a complete Z80 interpreter; not used in production Shinobi translation.

## [0.2.0] - 2026-11-04

- **Changed:** Added a separately discoverable production Z80 source-admission ABI (`rd_z80_source_gate_v1`) to the existing independently buildable DLL. The historic harness interpreter ABI remains unchanged, and only well-defined opcode lengths are independently checked; prefixed IX/IY lengths are labelled unverified rather than guessed.
- **Validation:** The new production CPU gate regression suite checks original source authentication, actual DLL dispatch, opcode-length rejection, active binary hash validation, alternate-implementation rejection and explicit fallback. Existing targeted CPU/harness regressions continue to run.
- **Compatibility:** Original `rd_get_plugin_v1` and `RD_ABI_VERSION` unchanged. RecompDev's native compilation and execution still use the preserved v0.4.0.45 P-code backend; this CPU DLL admits authenticated instruction bytes before translation, not replacement of instruction execution.
