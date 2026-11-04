# v0.2 — Isolated v0.4.0.45 P-code game DLL bridge

Compared with the already Windows-validated v0.1.1:

- Added `tools/build_pcode_plugin.py`: imports the **unchanged** v0.4.0.45 `nativepilot.generator`, validates Ghidra-format source evidence including bank overlay SHA and per-instruction hashes, lowers supported P-code and generates a shared-library translation module.
- Added shared bus and Ghidra register bridge, explicitly restricted to visible Z80 CPU registers; unmapped register / user ops not compiled.
- Added generated game module, sample developer-created ROM + source-attested synthetic function exports, manifest with instruction provenance and rejection reasons.
- Added `--case rom`, `--rom`, `--entry` and full source SHA256 / length verification using the generated DLL's identity exports.
- Added generated native -> fallback -> generated native resumption with ROM bank switching and dual machine substitution tests.
- Added Windows build/test guide, owner-ROM script, Clang and GNU C++ tests, SHA256 known vectors.
- Preserved v0.1.1 original plugin ABI and all 12 regression tests, kept production RecompDev v0.4.0.45 untouched.

**Not included:** real owner ROM or corresponding genuine Ghidra export, full Z80 ISA, actual game gameplay, interactive display/audio, PS1/Mega Drive backends, output ROM independence or Windows compiled acceptance for v0.2.
