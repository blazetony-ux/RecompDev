# RecompDev v0.4.0.30 — Cross-ISA Source-Supported Recovery

This release changes the **static conversion engine**, not just the UI:

- `scan --recover-indirect` invokes a conservative bounded, source-backed local-constant transfer recovery plugin for **M68000** and **MIPS**. `scan` without this flag retains previous discovery results so a direct comparison is possible. Recovered transfers are treated as *static candidates*, not executed instructions or proven whole functions.
- The M68000 plugin resolves PC-relative `JMP`/`JSR` and narrowly defined local register constants from `MOVEA.L #imm`, `LEA abs.W/L` or `LEA d16(PC)` into an address register followed by `JMP`/`JSR (An)`.
- The MIPS plugin resolves locally contiguous `LUI; ORI/ADDIU; JR/JALR` patterns and direct constants from the zero register; it respects the pipeline's existing MIPS delay-slot model and rejects ambiguous incoming paths.
- A finite 8-pass fixed-point walk revalidates earlier recovered register edges after discovering new paths and fails closed on unresolved ambiguity. Recovered edges carry SHA-256 digests of supporting source instructions and the destination instruction. The graph importer checks that hashes match registered observations.
- `benchmark-discovery` starts its own **clean** SQLite database and runs baseline/enhanced discovery against the same authenticated source, decoder, instruction budget, and entry seeds. It writes `benchmark-result.json`, per-scan flow evidence and `recovery-queue.json`, a source-identified list requiring independent confirmation before native code generation.
- The Catalogue now displays native campaigns in a **separate native execution history section**, keeping static graph counters distinct. The evidence reader discovers all numbered `integrated-native-vNNNN` directories without a fixed list and verifies authenticated historic source identity and event/host evidence.
- All pre-existing v0.4.0.29 Z80 native pilot, continuous host, neutral input and headless runtime paths remain in place, and are retested.

## How to test with your original game binaries (owner-local Windows PowerShell)

First install the ZIP to `C:\Projects`. There is **no ROM or PlayStation executable bundled**.

Full verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.30\Verify-v0430.ps1'
```

Sonic the Hedgehog (Mega Drive/M68000), same vector seeding as your 1,274 / 54 baseline:

```powershell
$r='C:\Projects\RecompDev-v0.4.0.30'; py -3 "$r\recomp.py" benchmark-discovery --input 'C:\Roms\MD\Sonic The Hedgehog (USA, Europe).md' --format megadrive --seed-vectors --max-instructions 100000 --expected-sha256 46160baa06362c711c9f1a5017cb7371026444936c8af5e93a78996cf32ff2a6 --out "$r\evidence\benchmarks-v0430\sonic"
```

Ridge Racer (PS-X EXE/MIPS), same no-extra-seed configuration as your 14,222 / 213 baseline:

```powershell
$r='C:\Projects\RecompDev-v0.4.0.30'; py -3 "$r\recomp.py" benchmark-discovery --input 'C:\Projects\Evidence\RecompProjects\ps1-ridge-racer-68468e09be\sources\boot.psx' --format psx-exe --max-instructions 100000 --expected-sha256 bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5 --out "$r\evidence\benchmarks-v0430\ridge"
```

Do not reuse an existing benchmark output database; each benchmark is immutable. The benchmark prints exact baseline and enhanced metrics. Inspect `recovery-queue.json` and supporting instruction hashes before treating newly discovered targets as functions.

## Qualification limits

- Linux tests cover source-encoded M68000/MIPS synthetic fixtures, including negative/fail-closed cases. **Actual Sonic/Ridge Racer improvement is not asserted**: their original binaries are not available in this build environment. Run both commands on the owner PC and share the results.
- Recovered static M68000/MIPS addresses are **not** compiled into playable native PC games in v0.4.0.30. A restricted synthetic M68000 path exists in earlier releases; there is no qualified general MIPS native backend.
- Authenticated Shinobi continuous native execution remains a distinct experimental capability. No Z80-independent semantics/MAME parity, sound or video correctness, gameplay or automated repair is claimed.
- External Ghidra/Rizin function-boundary reconciliation remains incomplete. Queued edges require independent confirmation; the pipeline does not silently promote candidates into a verified or playable native binary.
