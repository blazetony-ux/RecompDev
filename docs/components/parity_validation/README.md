# Independent native parity capture comparison

**Scope:** `production-diagnostics`. **Version:** `0.1.0`. Registry: `workspace/components.json`.

`RecompDevParity.exe --reference reference.json --candidate candidate.json` reads two explicit immutable, bounded capture records, without changing either. The contract `recompdev.parity.capture.v1` requires `rom_sha256`, `capture_role`, `capture_provider`, `clock_domain=host_output_frames`, `video_fingerprint_algorithm`, and a nonempty ordered `video_fingerprints` array of 16-character lowercase hex strings. Optional `input_sha256`, `audio_sha256` and `state_sha256` compare deterministic input identity, whole-run audio and state checkpoints. Source mismatch and, where available, input mismatch reject comparison. A mismatched first video frame, sample count, audio or state returns a diagnostic mismatch.

**Crucial limitation:** This only compares supplied data. It does **not** authenticate independent emulator provenance, prove faithful video timing, or validate unrecorded inputs, game state or sound. Even an exact pair returns `MATCHED_UNQUALIFIED` and `RECOMPDEV_GAMEPLAY_PARITY_QUALIFIED=FALSE`. The current preview can generate `candidate-capture.json` containing native output fingerprints, not independently trusted reference material. It does not fabricate audio, input or state equality. A trusted emulator capture adapter, identical input replay, source-attested checkpoints and quality gates are future work; parity remains **BLOCKED**.

This compiled tool depends only on a common JSON schema, not on the SMS, Z80, Mega Drive, MIPS or any controller runtime plugin. Read-only provider adapters may independently emit the same contract.
