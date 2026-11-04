# v0.4.0.32 handoff

Completed: conservative 8-step MIPS register-constant recovery, source-attested native code generation and CMake compilation for restricted M68000/MIPS subsets, bounded multi-ISA coordinator, generic first-difference checkpoint verifier, barrier triage. Retained Windows-verified v0.4.0.31 Workbench and Z80 host. Every new component is game-independent.

Outstanding highest priority: 1) real original game source-derived instruction compilation (expect unsupported hardware/ISA boundaries), 2) actual PlayStation MIPS unresolved target evidence (Ridge Racer's 81 barriers unresolved in v0.4.0.30), 3) independent original machine checkpoint *capture and alignment* not only comparison, 4) banked dynamic code recovery with proof, 5) CPU semantics/IRQ/device parity for Z80, 6) automatic independent repair proof, 7) multi-system console runtime. Do not claim complete x64 ports or autonomous code repair.

Do not require Shinobi diagnostic rerun for tests of generic MIPS/M68K functions or native history. Unfamiliar inputs require adapters and independent oracle evidence. All source code under multisa/ and adapters/ avoids commercial game-specific offsets and IDs.
