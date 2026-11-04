# RecompDev v0.4.0.10 — Autonomous Recovery & Verification Engine

RecompDev is a **multi-game, multi-console native recompilation Workbench**, not a Shinobi converter. Shinobi is an important regression test, not a title-specific implementation dependency.

## Windows installation (PowerShell)

Close the previous Workbench and download `RecompDev-v0.4.0.10-Autonomous-Recovery-Verification.zip` into Downloads. In PowerShell:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.10-Autonomous-Recovery-Verification.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.10\Run-Workbench.ps1'
```

Open `http://127.0.0.1:8777/discovery`. Keep older RecompDev releases installed; the new installation makes a separate `catalogue.v0410-working.sqlite` copy, preferentially from v0.4.0.9. Previously authenticated bank exports are reused only after ROM byte-hash verification. ROMs are not shipped.

## New in v0.4.0.10

- **Authenticated physical-address dependency graph.** `nativecore/dependencies.py` records decoded instruction nodes, explicit branches/fallthrough and unresolved physical-ROM targets per source SHA-256, without confusing banked addresses.
- **Bounded branch prefetch.** The common recovery controller can recover up to two additional attested, statically linked code entries before rebuilding. It never guesses an indirect target's dynamic mapper state; each Ghidra recovery must pass source-byte authentication.
- **Independent checkpoint comparison.** `nativecore/parity.py` compares ROM-hash-matched CPU states and event counters against a separately supplied reference file. `NOT_TESTED` is the default, mismatches block false parity claims, and sampled equality is not proof of complete parity. No external reference emulator is bundled or automatically invoked.
- **Workbench visibility fix.** Autonomous Discovery and Native Recompilation show native progress by imported game, using immutable source identity. Old structural ROM coverage, Ghidra candidates, translated instruction records, native execution steps and independent verification are separate measurements. A game with native progress is visible even when older per-function conversion tables are empty.
- **Multi-game regression checks.** Two independently constructed Z80 test cartridges continue through compiled fixed-vector recovery without title-specific code. 68000 and MIPS have shared capability reporting and preparation, but their native execution backends are **not implemented**.

## Run a native test

Open `http://127.0.0.1:8777/execution`, select a prepared Master System game, and choose an execution budget, recovery-attempt budget and 0–2 related branch-prefetch entries. Optionally configure up to eight RAM watchpoints. Run **Autonomously recover, compile & trace native C++**. Report and compiler output go under `evidence/native-pilot-v0410/jobs/<job-id>`.

### Independent parity evidence (optional)

Place a valid `recomp-independent-checkpoint-reference-v1` JSON document from a genuinely independent reference system under `evidence/independent-reference/`. Enter only its simple `.json` filename in Workbench. Fields include ROM SHA-256, `independent_source`, and sampled `checkpoints` with matching native step indices. The current comparison cannot align disparate CPU timing models automatically, so it is strictly an opt-in *sampled-state comparison*, not a turnkey reference execution integration.

## Known limitations

- Z80 compilation and Master System mapper/VDP/IRQ integration remain experimental and not cycle-accurate. A good step count is not evidence of game correctness or playable output.
- Batch prefetch only follows attested, statically decoded branch targets. Indirect and dynamic mapper edges need reference traces or further recovery, and missing code safely stops.
- No independent reference trace has been supplied for Shinobi; parity remains **NOT_TESTED**.
- A **second real commercial game** has not yet been run through this release. Two separate synthetic Z80 cartridges establish reusable behaviour in tests, not whole-game compatibility.
- Native 68000/Mega Drive and MIPS/PlayStation execution have not yet been integrated with this experimental pipeline.
- Workbench source coverage remains *structural discovery* and should not be confused with code-recovery or parity coverage.

## Diagnostic files requested after Windows runs

Upload a ZIP of the new native job directory minus `native-project`, including `pilot-report.json`, `worker.log`, `execution.log`, dependency graph/frontier metadata and any `parity-report.json`. Do not include copyrighted ROMs.
