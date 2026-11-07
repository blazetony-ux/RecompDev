# rd_cpu_z80 — independent changelog

## [0.5.1] - 2026-11-07

- **Changed:** Source-attested native lowering now handles `ED B0` (LDIR) and `ED B8` (LDDR), sharing the existing LDI/LDD byte-copy and documented flag semantics. A nonzero post-decrement BC sets the next guest PC to the same instruction; a zero count falls through. No game-specific address table or runtime-interpreter fallback.
- **Validation:** The `v04910_source_lift_block_copy_repeat` synthetic regression builds full native applications for both directions and executes three distinct ROM-sourced bytes into SMS RAM, asserting repeat/exit PCs, BC/HL/DE, watched destination bytes and 21/16 T-state timing. The owner observed the second Shinobi gap at `0xB2EE` after moving from `0xB2E1`; the new full-ROM Windows execution remains pending.
- **Compatibility:** No public CPU/plugin ABI changes, original LDI/LDD behaviour and frozen historical trees remain intact. Candidate only; no Windows gameplay parity or 1,800-frame promotion claim.

## [0.5.0] - 2026-11-06

- **2026-11-07 candidate continuation:** Source-decoded Z80 JR NZ/Z/NC/C now emits direct conditional native C++; abstract relative/conditional control flow and flags-only operations preserve verified mapper state. This supports a reusable runtime-gap CALL/PUSH/JR/RET test with observed stack evidence, not a Shinobi title-specific opcode path. Windows validation and extended gameplay still blocked.
- **Changed:** Source-verified native lifting for Z80 `LDI/LDD`, ED block I/O (`OUTI/OUTD/OTIR/OTDR/INI/IND/INIR/INDR`), `IN/OUT`, CB `BIT/RES/SET`, conditional `RET`, stack/call/return, selected loads and register arithmetic. Conservative mapper-state propagation now distinguishes pure port I/O and CB BIT reads from possible memory writes. The plugin exposes reset/IM1/NMI vectors via a CPU-owned optional ABI extension.
- **Validation:** Real 256 KiB commercial Shinobi ROM was hashed and exercised on Linux. A source-verified C++ project emitted 4,843 instructions with zero rejections in the selected available evidence set and ran 338,531 native steps / 64 frames with video device writes, before a remaining source-code gap. Tests preserve old synthetic CPU interpreter and reject forged provenance.
- **Compatibility:** Optional CPU ABI extensions only; original `rd_get_plugin_v1` bus/runtime plugin descriptor remains intact; no Shinobi-specific offsets, title checks or immutable source changes.

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
