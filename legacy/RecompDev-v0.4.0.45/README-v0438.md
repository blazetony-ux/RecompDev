# RecompDev v0.4.0.38 — Conditional Z80 control-flow correctness

This release applies the source-verified generic conditional CALL/RET P-code lowering correction, plus the independently compiled Master System TH-line feedback correction. No ROM bytes or generated commercial-game code are bundled.

## Evidence and limits

- In the compiled source-attested **owner Shinobi** translation, correcting Z80 conditional control alone changed 120-frame output from black to a visible Sega logo, with nonzero CRAM. That experiment is documented in the investigation checkpoint; it is **not** a claim that v0.4.0.38 combined recovery + TH correction is playable.
- Correcting the separate SMS TH feedback operation yielded the expected port 0xDD feedback in a compiled independent test and moved the local Shinobi state to `C006=0x81`, but exposed an untranslated ROM address around `0x02A8` in the un-recovered local project.
- The shared Z80 generator now protects stack and next-PC side effects of conditional CALL/RET behind the same instruction-local CBRANCH used by Ghidra P-code. Unsupported P-code control-flow shapes remain rejected.
- On non-Shinobi games, the fix passes generic compiled CALL/RET, TH-line, inherited compiled-output and full regression gates. **Authentic six-other-game improvement or no-regression is owner validation pending** because those ROMs are not available here.
- The new seven-game campaign compares frame progress, recovery attempts and blockers against the prior hash-identified v0.4.0.36 campaign, without asserting correct gameplay or MAME CPU equivalence.

## Windows PowerShell: install, verify, launch

Close the old Workbench first.

1. Extract: `Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.38-Conditional-Control-Cross-Game.zip" -DestinationPath 'C:\Projects' -Force`
2. Verify: `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.38\Verify-v0438.ps1'`
3. Workbench: `powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.38\Run-Workbench.ps1'`

## Cross-game qualification (one command)

`py -3 'C:\Projects\RecompDev-v0.4.0.38\tools\Run-SMS-Campaign-v0438.py'`

The runner uses the existing seven filenames under `C:\Roms\MASTERSYSTEM`, the new independent working catalogue, 120 frames and identical recorded execution/recovery budgets for comparison. Its evidence ZIP includes `baseline-comparison.json` and excludes ROMs, generated machine code, executables and A/V capture bytes. **Upload the ZIP printed as `EVIDENCE_ZIP=`.** Per-game errors never stop other games.

A larger frame count means progress, not correctness. Validity checks bind comparisons to ROM SHA-256 and identical execution budgets. If the game fails earlier, the result is explicitly classified as a regression observation, not hidden.

## Release acceptance

`Verify-v0438.ps1` checks manifest integrity, previous compiled native-output qualification and new conditional/TH compiled gates, full repository unit tests and bridge tests. Earlier versions and catalogues are kept; the Workbench imports the v0.4.0.37 catalogue into a separate v0.4.0.38 copy.

Independent MAME/native instruction parity, Shinobi gameplay, and six-game commercial ROM qualification are **not established** by the local compiled tests.
