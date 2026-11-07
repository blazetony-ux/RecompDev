# rd_translation_pcode — independent changelog

## [0.3.0] - 2026-11-07

- **2026-11-07 WindowsFix2:** Corrects the large full-game code generation path: `rd_generated_translation` now declares its own maintained runtime include directories. The small fixture compiled because it uses executable-level include paths, masking MSVC `C1083` on the partitioned library.
- **Validation:** Added configure/build/link of both native applications for a 600-instruction, 24-partition synthetic export to the existing CTest; prior Windows release CTests were green but the real generated Shinobi project failed before execution. The updated test passes locally on Linux; the new Windows MSVC result and gameplay parity remain unverified.
- **Compatibility:** No C++ State layout, plugin C ABI, emitted instruction semantics, verified source bytes, or partition assignment changes. No external historical source changes.

- **Changed:** Full-game translation templates now originate under maintained `runtime_sms/templates`, not protected `legacy` paths, and the generated CMake project builds the SMS native runtime, Mode-4 video and host presentation as three independent DLLs. Source-attested lowering, stable C++ partitions and source-verified recovery seeds remain intact; JSON node limit admits a legitimate large 2.23-million-node Ghidra export under the existing size and depth bounds.
- **Validation:** Linux native translator differential CPU-state/mapper/timing test builds and executes newly generated binaries with independent DLLs; static boundary test ensures no frozen production dependencies. The 120-frame actual Shinobi run belongs to the *previous* candidate, not this cutover, and cannot be claimed as new renderer parity.
- **Compatibility:** Translation request/result C ABI remains unchanged; generated native game still requires matching source ROM at runtime and uses a C++ State ABI within one compiler toolchain. Windows/MSVC and second-ROM compatibility are pending.

## [0.2.0] - 2026-11-06

- **Changed:** Consumes attested newly decoded instructions from interchangeable CPU plugin, including verified `RET` paths, while retaining the original P-code lowering. Splits large generated native C++ across 24 physical-address-stable partitions, so one added verified instruction changes only its owning translation object. Accepts controller-verified runtime-gap discovery reports for successive native recovery cycles.
- **Validation:** Synthetic generated code compiles/executes with banked calls and Z80 block I/O; forged source bytes are rejected. Independent 600→601 instruction test verifies exactly one generated partition changes. Real Shinobi evidence compiled on Linux, with 4,843 emitted / zero rejected from the selected source exports and discovery report; pilot ran 64 frames, **not** historical 1,800-frame parity.
- **Compatibility:** Existing C translation ABI is unchanged; original runtime C++ and historical Python/Ghidra sources are copied/consulted but not altered. Automatic end-to-end Ghidra and runtime-triggered recovery loops are not yet fully ported.

## [0.1.0] - 2026-11-06

- **Changed:** Introduced a compiled, interchangeable C++ translation DLL with strict ABI and Ghidra P-code source-provenance checks, optional reuse of legacy bank exports, and generation of either the preserved nativepilot full runtime or a source-specific C ABI game DLL. Includes explicit translation failure diagnostics and source hash matching.
- **Validation:** Differential synthetic Ghidra-export fixture generates and compiles both fresh C++ runtime binaries and a game DLL, comparing bank, CPU register, memory-write and timing effects against the immutable Python generator, plus negative ROM/byte-hash/format tests. Linux available test suite passes; Windows real commercial-ROM Shinobi equivalence is not yet demonstrated.
- **Compatibility:** Frozen original source, native execution protocol, hardware plugins and permanent Git-managed installer unchanged. This plugin does not rewrite Ghidra or the existing automatic recovery driver and still needs original ROM at generated native application startup for source attestation.
