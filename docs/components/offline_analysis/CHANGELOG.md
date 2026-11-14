# offline_analysis — component changelog

## [0.3.0] - 2026-11-14

- **Changed:** Tighten CPU/machine memory-write precision for safe known Z80 stack/register-indexed and counted-copy ranges while preserving explicitly unknown mapper/control aliases. Add conservative intersection joins for speculative call continuations, M68000 SP/exception-return handling and MIPS conditional link distinction; format/ISA/machine separation unchanged.
- **Capability:** Source-hash-audited v35/v36/v37 candidate comparisons, repeatable old evidence baselines, and a new optional CPU-provider-owned minimal native-control-flow probe from independently attested static instructions. The proof compiles and runs C++ for authored Z80 and 68000 loops; it is not a game-runtime translator and cannot lift unsupported instruction semantics.
- **Validation:** 13 precise-memory/comparison cases, five native-handoff safety/compilation cases, local-Git divergence checks and compiled-controller generic dispatch; owner Windows full 108-CTest suite and 642-file preservation still required. No real-game extra candidate count, hardware parity or standalone game output claimed.
- **Compatibility:** `ANALYSIS_ABI=2` stays unchanged with optional `lift_probe`; native DLL and active game/runtime ABI are untouched. `-PublishOrigin` is still opt-in and never pushes game-derived source.


## [0.2.0] - 2026-11-14

- **Changed:** Introduces immutable CPU abstract-register facts, CPU-plugin `initial/key/advance/indirect` hooks and machine-only mapping state with an explicit version-2 analysis provider ABI. The universal traversal owns bounded call/return contexts; machine plugins alone interpret ROM banking and memory-mapped write addresses.
- **Capability:** Resolves statically known Z80 HL/IX/IY branch targets and some known mapper writes; M68000 LEA/An computed jumps; MIPS LUI/ORI/ADDIU register jumps, JAL/JR-RA returns and delay-slot ordering, without playing a game. Tracks resolved sites and contexts in source-hashed evidence.
- **Compatibility:** This replaces only offline analysis provider ABI v1; compiled/native plugin ABIs, gameplay runtime, frozen sources and generated game Git histories are unchanged. Unknown callee fallthrough is marked speculative instead of endorsed as reachable; indirect targets are never guessed; unsupported instruction lengths remain blocked; return-depth, worklist and register-context bounds are enforced. Source bytes, frozen histories, main/native Git and runtime activation remain protected.
- **Validation:** 16 new authored cross-ISA abstract-flow cases and a compiled-controller three-format end-to-end test, plus all v35 contracts and historical suites. No whole-game translation, user-ROM gameplay parity or generated native standalone export is asserted.

## [0.1.0] - 2026-11-14

- **Changed:** Introduced an independent CPU- and machine-neutral offline whole-ROM interrogation engine and versioned provider registry, with interchangeable file format, instruction-decoding and memory mapping implementations. The initial providers support static decoding of SMS/Z80, Mega Drive/M68000 and PS-X EXE/MIPS fixtures without any game execution.
- **Validation:** Dedicated invented source-fixture tests exercise three independent ISA formats, bank-register propagation, 16-bank inventory, unknown mapper/indirect target admission refusal, MIPS delay-slot handling, conservative 68000 length rejection, symlink refusal, source SHA consistency, output overwrite prevention and portable unknown-format results. A compiled-controller end-to-end CTest runs all three profiles through the same CLI.
- **Compatibility:** Does not replace native DLL plugin ABIs, the existing Ghidra/Rizin pipeline, live recovery, v0.4.9.34 standalone export, generated-source Git histories or 642 historical frozen files. No complete universal-ROM translation, CPU semantics, reference hardware parity or playable Mega Drive/PS1 output is claimed; these remain blocked.
