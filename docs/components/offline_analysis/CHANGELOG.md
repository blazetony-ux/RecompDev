# offline_analysis — component changelog

## [0.1.0] - 2026-11-14

- **Changed:** Introduced an independent CPU- and machine-neutral offline whole-ROM interrogation engine and versioned provider registry, with interchangeable file format, instruction-decoding and memory mapping implementations. The initial providers support static decoding of SMS/Z80, Mega Drive/M68000 and PS-X EXE/MIPS fixtures without any game execution.
- **Validation:** Dedicated invented source-fixture tests exercise three independent ISA formats, bank-register propagation, 16-bank inventory, unknown mapper/indirect target admission refusal, MIPS delay-slot handling, conservative 68000 length rejection, symlink refusal, source SHA consistency, output overwrite prevention and portable unknown-format results. A compiled-controller end-to-end CTest runs all three profiles through the same CLI.
- **Compatibility:** Does not replace native DLL plugin ABIs, the existing Ghidra/Rizin pipeline, live recovery, v0.4.9.34 standalone export, generated-source Git histories or 642 historical frozen files. No complete universal-ROM translation, CPU semantics, reference hardware parity or playable Mega Drive/PS1 output is claimed; these remain blocked.
