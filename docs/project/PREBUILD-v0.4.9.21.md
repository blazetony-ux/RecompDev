# v0.4.9.21 scope and acceptance — native monitor, parity evidence, bounded recovery

**Approved direction:** generic compiled C++ controller plus interchangeable CPU/machine/analysis/translation/presentation/monitor services. Do not put Shinobi, Z80 or Master System rules in the controller. Binding [DEVELOPMENT-CONTRACT.md](DEVELOPMENT-CONTRACT.md) and owner-approved [PREBUILD-v0.4.9.7.md](PREBUILD-v0.4.9.7.md) remain authoritative.

**Owner baseline:** v0.4.9.20 locally installed `main` commit `b3a2db76080899307bea0385aea41648c1b3843a`, full 69 Windows CTests passed, 642 protected original files unchanged, and real Shinobi 1,800 host output frames reached. CPU/VDP/audio/input and gameplay reference parity remains unverified; no non-neutral key input was recorded.

**Boundaries to build:** standalone native Win32 read-only diagnostics subscriber; explicit final native guest device, sampled event and host frames as separate clock domains; CPU-neutral native candidate/reference frame comparator that does not claim gameplay parity; configurable 128 bounded immutable cycles with old job provider pinning intact. Python remains for Ghidra/Rizin and preview work orchestration; monitor must be native on Windows. Preserve all original sources, original evidence, and production-active DLLs.

**Acceptance:** Linux C++ build, 72 or more CTests including old 69 and new native monitor/parity/contracts, ROM-free candidate ZIP with bounded SHA manifests, Windows owner MSVC full CTest and visual GUI verification, strict source/ROM/input gates. **BLOCKED**: independent reference emulator captures and actual interactive game-state/audio/video parity, second ISA/console validation, complete legacy migration.
