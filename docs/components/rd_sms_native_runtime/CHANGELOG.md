# rd_sms_native_runtime — independent component history

## [0.1.1] - 2026-11-07

- **Changed:** Generated continuous native app emits the actual stopped Z80 stack pointer (register pair 68/69) and loaded source-ROM byte count alongside PC, physical offset, mapper and execution status. Bounded recovery can create an honestly labelled application-stop seed rather than fabricating a pilot stop.
- **Validation:** Synthetic two-ROM native orchestrator test compiles and executes a generated application and checks the new SP and source-length fields; real ROM gameplay and machine parity are still blocked.
- **Compatibility:** Existing runtime DLL ABI and machine/CPU logic remain unchanged. The observed-state reporting addition is additive; the old unmodified historical runtime remains a frozen comparator only.


## Windows MSVC source compatibility fix — 2026-11-07 (candidate revision)

- **Fixed:** The exported `rd::State` class incorrectly declared `static constexpr` data members which MSVC rejects with C2487. These fixed timing and event bounds are now inline enum values without DLL data-member symbols. No runtime algorithms, values or ABI data layout were changed.
- **Validation:** Linux compile and regression checks, source-package checks, and source-level export-compatibility regression; full MSVC compilation must still be verified on the owner Windows build.

## [0.1.0] - 2026-11-07

- **Changed:** Introduced an independently compiled native Master System runtime DLL from a maintained port of the previous working machine-state, timing, mapper, VDP/PSG and P-code memory operations. Original `legacy` runtime sources remain frozen and are used only as offline regression reference; screenshot generation calls the external Mode-4 video DLL.
- **Validation:** New compiled ABI smoke verifies source bank switching, physical ROM bank mapping, Mode-4 rendering and headless RD_Host frame presentation, plus fresh generated native-project CPU-state parity with the preserved generator on Linux. Windows DLL import/export, 1,800-frame Shinobi execution, authentic images and controls are not yet confirmed.
- **Compatibility:** New C ABI version-probe `rd_sms_native_runtime_abi` returns `0x00010000`; actual `rd::State` and P-code evaluator operations currently cross a C++ ABI and therefore require a matching compiler toolchain. Independent video/host DLL dependencies and matching original ROM remain required. Immutable originals are not overwritten.
