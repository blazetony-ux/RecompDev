# Production CPU bridge — independent component history

## [0.1.0] - 2026-11-04

- **Changed:** Introduced a production-workflow Z80 gate that consumes real physically authenticated source instructions and validates the active independent CPU DLL version, on-disk binary SHA-256, export identity and extension ABI before allowing native recovery to continue.
- **Validation:** Automated synthetic-ROM export checks exercise the frozen actual Ghidra P-code verifier, native DLL admission, rejecting alternate gate, fail-closed tamper handling and explicit legacy fallback; full existing CTest suite remains mandatory.
- **Compatibility:** No modification to frozen legacy translation or native recovery modules. A selected CPU DLL controls source admission, but does not yet execute or translate native Z80 operations. Other platforms must not be routed through this Z80-only interface.
