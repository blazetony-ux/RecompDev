# rd_artifact_store component changelog

## [0.1.0 Windows validation correction] - 2026-11-08

- **Fixed:** Atomic publication now creates a short temporary sibling filename rather than appending a nonce to the final content-hash filename. This prevents the Windows `ARTIFACT_WRITE_FAILED` error caused when the capsule manifest's temporary pathname exceeded the traditional Win32 `MAX_PATH` limit during test `v04925_universal_artifact_store`.
- **Safety:** Temporary files remain within the destination directory, with content/immutable-collision checks and atomic rename unchanged; no change to source identity, cache schema, CPU or hardware plug-in semantics.
- **Qualification:** Windows full-suite validation of the corrected candidate is pending; original v0.4.9.25 candidate failed 80/81 CTests and was not installed.

## [0.1.0] - 2026-11-08

- **Changed:** Introduced a standalone native provider with C ABI v1 and content-addressed immutable storage for generic CPU/hardware/host-labelled artifacts. A transitional capsule adapter migrates complete source-attested recovery input into portable object storage independent of old diagnostic trees.
- **Validation:** Native C++ fixture tests check multiple unrelated architectures, tamper refusal, relocation after removal of original evidence, binary C ABI operations, and independently rechecked synthetic Ghidra plus physical bank-overlay imports.
- **Compatibility:** No new instruction or machine semantics, compiled game DLL reuse, in-place hot-load, interactive state restart/replay, or gameplay parity is claimed. v23/v24 original histories remain untouched, and cache reuse still undergoes existing source/tool/provider checks.
