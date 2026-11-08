# parity_validation component history

## [0.1.0] - 2026-11-07

- **Changed:** Added an independently built C++ capture comparator, generic JSON v1 contract, strict same-ROM and same-input-hash admission, per-frame video fingerprint comparison and optional audio/state hashes. A source-verified native preview can emit video-only candidate evidence for a future independent emulator reference.
- **Validation:** Cross-platform C++ contracts cover a matching pair, first video mismatch, rejected ROM and different deterministic input hashes; actual independent Master System emulator data are not supplied.
- **Compatibility:** Standalone service has no CPU, machine or game DLL linkage and reports `RECOMPDEV_GAMEPLAY_PARITY_QUALIFIED=FALSE` even on matching fingerprints; reference provenance, hardware/audio/state/input parity remain BLOCKED.
