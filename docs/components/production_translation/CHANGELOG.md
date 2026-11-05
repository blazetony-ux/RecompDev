# Production translation — independent changelog

## [0.1.1] - 2026-11-05

- **Changed:** Moved CMake/MSBuild generated native-game compiler intermediates into a short, deterministic directory beneath external `RecompDev-Build/native/`. Publish only the two required resulting executables into the legacy generated-project compatibility location. Preserve complete CMake configuration/build logs even on failure; never report failed compilation as successful execution. Allow explicit previously authenticated history roots to seed the preserved ROM-byte-verified recovery cache.
- **Validation:** Authenticated synthetic native game builds from a deliberately deep evidence path; SHA-256 verification of unchanged translated source and protected historical files; negative build-failure and history-activation tests. The prior Windows `MSB6003` build-tree problem is expected to be mitigated, but the exact OS failure cause remains unconfirmed.
- **Compatibility:** The original `nativecore.continuous_recovery_v0436` engine and `nativepilot.generator` remain byte-for-byte unchanged. The controller, all DLL versions, live catalogue and previously captured evidence are untouched. No guest parity claim.
## [0.1.0] - 2026-11-04

- **Changed:** Added a SHA-256-pinned production translation provider that invokes the full original v0.4.0.45 P-code generator through the real preserved native recovery driver. Retained the complete original semantics and banking-aware reset/replay rather than replacing them with a small opcode implementation.
- **Validation:** Byte-for-byte authenticated synthetic native-project generation parity, two bounded real native-compilation paths, verified original-generator source hash and a negative test for modified provider files. Existing preservation and regression tests remain required.
- **Compatibility:** This is a production Python source adapter; the compiled controller, Z80 v0.2.0 DLL, other runtime DLLs and frozen v0.4.0.45 source versions remain unchanged. Explicit `legacy-direct` fallback remains available, and real-game 600-frame parity is still pending.
