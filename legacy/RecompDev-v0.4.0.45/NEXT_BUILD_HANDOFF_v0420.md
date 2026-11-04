# v0.4.0.20 consolidated milestone handoff

**DO NOT resume the repetitive 'run Shinobi and increase steps' cycle.**
The core goal is a reusable, source-attested native conversion pipeline with
independent behavioural evidence, not console-title workarounds.

Implemented: shared campaign runner, explicit code/bank-origin reference anchor
contract, fail-closed hardware checkpoints, quarantined synthetic holdout
semantic recipe search, Windows native-host demonstration, restricted M68000
C++ lowering with separately implemented Python fixture oracle, and regression
gates. See README-v0420.md and BUILD_VALIDATION_v0420.json.

**Work required before claiming a playable game**:
- In owner Windows environment, authenticate live MAME BIOS/cartridge/mapper
  reset mode and register/checkpoint capture for exact native reference alignment.
- Connect analyzer-export provenance to incremental *executable* Z80 codegen;
  check supporting semantics with independent CPU instruction oracle and
  indexed shared recovery recipes. Reject unresolved CFG edges, don't guess.
- Qualify transactional device state, ordered bus effects, frame/video and
  audio output; then connect the host window/audio/input hooks to generated
  native gameplay rather than a separate synthetic test pattern.
- Extend M68000 decoding (flags, memory, branches, traps, exceptions, bus,
  multi-CPU) and run a truly independent external reference engine, including
  authentic target programs. Do not call the restricted fixture backend complete.
- Implement safe source-repair proposals with user-approved change scope,
  generated adversarial regression, live dependency retries, atomic rollback,
  and independent holdout authorization. The existing exercise writes recipes
  but **does not patch production shared code**.

Never imply that a green architecture gate means verified game parity. The
release must not include owner ROMs, Ghidra/Rizin/MAME binaries, or data from
licensed commercial games. Running any new genuine-game pilot requires a
specific unanswered engineering question, not merely a release number.
