# Production translation — independent changelog

## [0.1.0] - 2026-11-04

- **Changed:** Added a SHA-256-pinned production translation provider that invokes the full original v0.4.0.45 P-code generator through the real preserved native recovery driver. Retained the complete original semantics and banking-aware reset/replay rather than replacing them with a small opcode implementation.
- **Validation:** Byte-for-byte authenticated synthetic native-project generation parity, two bounded real native-compilation paths, verified original-generator source hash and a negative test for modified provider files. Existing preservation and regression tests remain required.
- **Compatibility:** This is a production Python source adapter; the compiled controller, Z80 v0.2.0 DLL, other runtime DLLs and frozen v0.4.0.45 source versions remain unchanged. Explicit `legacy-direct` fallback remains available, and real-game 600-frame parity is still pending.
