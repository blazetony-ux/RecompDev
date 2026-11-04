# RecompDev v0.4.0.24 — engineering handoff

Implemented: versioned host adapter registry; source-authenticated integrated native pilot → compiled continuous host job; optional live Windows presentation; deterministic headless frame/audio replay; read-only cross-release source-keyed event-verifying evidence view; Windows v0423 regression hotfix.

Validated locally: two different synthetic Z80 programs, including one that reaches a frame boundary and produces a WAV and PPM, one that stops correctly at untranslated banked code; hardware-event tamper rejection; deterministic repeated headless audio/video; second-system explicit-block test. All regression suites must pass before release.

Still OPEN: actual MSVC GUI on the owner Windows computer, authentic MAME instruction/BIOS-bank-aligned parity, complete Z80 flags/cycle/interrupt semantics, Master System VDP/PSG hardware fidelity, upstream analyzer-to-native repair promotion, authentic playable Shinobi. Do not treat executed steps, compilation, matching hash, or frame delivery as gameplay parity.

Next engineering priorities: independent reference alignment (source+bank+CPU-state matched, not event-number heuristic), verified shared Z80 semantic repairs, cycle-accurate SMS hardware adapter testing, automatic bounded tool-driven recovery and native regeneration, authentic host input/audio/video qualification. All must remain source-attested and game-agnostic.
