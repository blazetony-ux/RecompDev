# RecompDev Modular Harness PoC v0.2 — Windows

## 1. Build & verify the standalone sample

Extract the **v0.2 Source** ZIP in a *new* directory, e.g. `C:\Projects\ModularHarness-PoC-v0.2`. Do not overlay v0.1.1 or RecompDev v0.4.0.45.

Requirements: VS 2022 C++ Build Tools (x64 MSVC), CMake, Python 3.

```powershell
cd C:\Projects\ModularHarness-PoC-v0.2
powershell -NoProfile -ExecutionPolicy Bypass -File .\Build-Windows.ps1
```

Expected: **18 tests pass**. Tests include the original v0.1.1 12, a generated P-code game DLL, fallback/resumption, bank-qualified dispatch, bad source rejection, and SHA256 standard vectors. Output: `build-win\bin\Release\RecompDevHarness.exe` and DLLs.

## 2. Run the sample generated game DLL

```powershell
.\build-win\bin\Release\RecompDevHarness.exe `
  --plugin-dir .\build-win\bin\Release `
  --game rd_game_recomp_v0445 `
  --case rom --rom .\examples\recomp-pcode\synthetic.sms `
  --validate --out .\build-win\reports\my-pcode-test
```

Expected: `native=8 fallback=2 ... differential=PASS`. The fixture's interpreter is deliberately small; parity covers only its supported instructions. `my-pcode-test.report.json`, `.events.jsonl`, `.ppm`, and `.wav` provide evidence.

## 3. Import an actual authenticated RecompDev export (optional)

Supply the **owner-local ROM** and the matching `recomp-function-pcode-v1` JSON emitted by v0.4.0.45 `ExportFunctionBodies.java` / its discovery pipeline. Bank overlay exports may also be supplied with `-BankExports`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Build-GameModule-Windows.ps1 `
  -Rom 'C:\Roms\MASTERSYSTEM\SomeGame.sms' `
  -Export 'C:\Evidence\SomeGame-functions.json' `
  -BankExports @('C:\Evidence\SomeGame-bank3.json') `
  -Steps 100
```

This (1) independently checks the ROM SHA-256, instruction bytes, overlay identity and supported P-code with the **original v0.4.0.45 verifier**, (2) emits C++ from the **original v0.4.0.45 lowering function**, (3) builds the game DLL, (4) executes under the generic harness, requiring exact source SHA-256 equality. The generated manifest records rejected instructions. It **does not** alter v0.4.0.45's catalogue or source.

A real export may encounter `UNSUPPORTED_Z80_OPCODE`, unimplemented register offsets or timing. This is *expected* at the current compatibility boundary. Do not claim native gameplay or full CPU accuracy. Start with very small step budgets; `-Validate` is meaningful only where the PoC interpreter supports the needed instructions. No game ROMs are shipped in this archive; `synthetic.sms` is author-created for testing.

**NOTE:** The v0.2 CMake target builds one generated game DLL at a time. Before switching to another game, preserve its generated `cpp`/manifest and corresponding DLL. Long-term per-game targets and multi-CPU ABI are not yet implemented.

## Isolation and source integrity

The PoC is entirely self-contained. Never build it in the original RecompDev folder. The harness only reads the supplied ROM at runtime and writes reports under `build-win/reports`. Its full-source SHA check rejects mismatched source images before guest execution. In native-only mode, untranslated code is rejected. Development/discovery mode may still require the original ROM, so **it is not yet a ROM-free final game port**.

## Restore the shipped synthetic acceptance fixture after compiling a different game

The synthetic tests expect the matching generated DLL and source. Regenerate the sample and rebuild before re-running the full test suite:

```powershell
py -3 .\tools\make_pcode_sample.py .\examples\recomp-pcode
py -3 .\tools\build_pcode_plugin.py --rom .\examples\recomp-pcode\synthetic.sms --export .\examples\recomp-pcode\function-export.json --bank-export .\examples\recomp-pcode\bank3-export.json
cmake --build build-win --config Release
ctest --test-dir build-win -C Release --output-on-failure
```

The harness's external-ROM mode verifies whole-ROM SHA-256. The sample exports are **synthetic**, not real Ghidra output.
