# rd_native_module_loader — independently versioned native library

## [0.1.0] - 2026-11-08

- **Changed:** - New CPU/machine-neutral `RD_NativeBlockV1` C ABI, source/CPU/semantics/machine/state/target compatibility validation, SHA-256 binary attestation, platform `LoadLibraryExW`/`dlopen` behind append-only immutable native module set and native block dispatch without CPU-specific logic.
- **Validation:** Native and generated Z80/SMS synthetic tests run on Linux; Win32 genuine ROM recovery, display continuity and compiled controller orchestration remain unverified.
- **Compatibility:** Versioned module ABI and legacy static runtime path are retained; prior CPU semantics and historical source unchanged. Same-compiler SMS State C++ ABI only; live automatic compilation remains BLOCKED.
