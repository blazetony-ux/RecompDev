# Next development milestone following v0.4.0.3

Validated so far: real UI POST can prepare a discovered ROM, insert an authenticated Z80 target and show candidate metadata. New grouped tasks are persistent. Genuine Ghidra-on-Windows and game-code semantic validation remain pending.

Next *reusable* features: independent Z80 disassembly/boundary reconciliation; verified banking/table semantics; typed Z80 P-code IR mapping into shared native C++ CPU-state runtime; SMS VDP/audio/input adapters; deterministic execution comparisons. Do not claim successful whole-function conversion until compared. Master System ROM is not a flat 64 KB program: 0xC000–0xFFFF is RAM.

Do not increase or re-enable risky broad default scans over unsupported formats, or claim a game has become C++-ready merely because its ROM is registered.
