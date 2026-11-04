# RecompDev v0.4.0.32 — Consolidated Multi-ISA Native Engine

This is a **source-attested engineering release**. It is not a complete game converter, CPU emulator, commercial game patch collection, full PlayStation/Mega Drive implementation, or claim of independent MAME parity. It preserves the v0.4.0.31 Windows-verified historical Shinobi evidence and Z80 native execution path.

## Shipped capabilities

1. **Native M68000 subset compiler** (`multisa/native.py`) translates explicitly supported decoded 68000 instructions to C++17 `switch` cases with encoded register/flag/control-flow effects. Includes MOVEQ, ADDQ/SUBQ.L on data registers, NOP, RTS, BRA/BSR, BEQ/BNE and selected absolute/PC-relative JMP/JSR. Unsupported instruction boundaries stop natively; no instruction-word interpreter fallback. Does not model hardware addresses, full status register, memory or exceptions.
2. **Native MIPS subset compiler** translates LUI, ORI/ANDI/XORI, ADDIU, selected register arithmetic/logical/shift operations, BEQ/BNE, J/JAL/JR/JALR and explicit delay slots. Untranslated, unmapped or invalid delay-slot paths remain blockers. No RAM, cache, coprocessor, exception, OS, GPU, load delay or PlayStation hardware model is represented.
3. **Generalised MIPS bounded constant discovery** (`adapters/indirect.py`) supports unique-predecessor, 8-instruction proof windows with source hashes, refuses ambiguous joins and unknown memory operations. This is an **additional static recovery pattern**, not a claim that authentic Ridge Racer barriers are solved.
4. **Universal conversion campaign** (`universal-campaign`) combines owner-local SHA-bound baseline/enhanced static discovery, source-hashed barriers, bounded native instruction emission, optional native compilation and execution into one recorded job. It categorises unsupported boundaries without pretending to repair them automatically.
5. **Independent-reference comparison contract** (`compare-checkpoints`) reports the earliest mismatch in two aligned, explicitly provided checkpoint streams, with source and initial-state SHA-256 guards. It cannot itself capture or verify a MAME reference: an independently obtained reference is required.
6. **Reusable barrier triage** (`triage-evidence`) classifies unresolved indirect transfer, mapping, delayed-branch, decode, system and budget categories into a deterministic investigation queue for any architecture supplying a valid flow evidence report.
7. **Previous capabilities retained:** Windows Workbench, cross-version source-hash history, Z80 native continuous guest runtime, null display/audio/controller outputs and M68000/MIPS static benchmarking.

No hard-coded commercial game offsets, patches or filenames occur in the new translator, comparator, triage or coordinator.

## Windows installation

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.32-Consolidated-MultiISA-Engine.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.32\Verify-v0432.ps1'
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.32\Run-Workbench.ps1'
```

Use **one command at a time** in PowerShell, after closing the old Workbench. The new release takes a separate snapshot from the existing working catalogue. Previously recorded campaigns are read, not rerun.

## Investigate genuine original owner binaries (not a native gameplay launch)

### M68000 / Sonic owner-local source

```powershell
$r='C:\Projects\RecompDev-v0.4.0.32'; py -3 "$r\recomp.py" universal-campaign --input 'C:\Roms\MD\Sonic The Hedgehog (USA, Europe).md' --format megadrive --seed-vectors --max-instructions 100000 --expected-sha256 46160baa06362c711c9f1a5017cb7371026444936c8af5e93a78996cf32ff2a6 --out "$r\evidence\multiisa-v0432\sonic" --compile --run-steps 1000
```

### MIPS / Ridge Racer owner-local PS-X EXE

```powershell
$r='C:\Projects\RecompDev-v0.4.0.32'; py -3 "$r\recomp.py" universal-campaign --input 'C:\Projects\Evidence\RecompProjects\ps1-ridge-racer-68468e09be\sources\boot.psx' --format psx-exe --max-instructions 100000 --expected-sha256 bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5 --out "$r\evidence\multiisa-v0432\ridge" --compile --run-steps 1000
```

Each command preserves a complete source-identity-bound report in its output directory. These real programs likely encounter **unsupported CPU instructions and console hardware immediately**; output such as `UNSUPPORTED_TRANSLATION` or `UNMAPPED_TRANSLATED_PC` is an expected, useful failure boundary rather than a qualified native game. Compilation proves only a supported restricted subset was compiled. The feature uses a CMake C++17 compiler for `--compile` and Capstone Python for discovery; missing dependencies fail visibly. Do not overwrite previous results; choose another output folder for repeated runs.

### Native code generation for any supported raw code fragment

```powershell
$r='C:\Projects\RecompDev-v0.4.0.32'; py -3 "$r\recomp.py" compile-native-slice --input 'C:\path\to\owned-code.bin' --format raw --isa mips --endian little --base 0x10000 --entry 0x10000 --max-instructions 100 --out "$r\evidence\multiisa-v0432\raw-slice" --compile --run-steps 1000
```

Change `--isa`, byte order, base and entry for the target you actually have. The tool does not infer these for raw input. Unsupported ISAs/containers must receive new ISA and machine adapters; there is no guaranteed automatic conversion of a previously unseen console.

### Independent checkpoint alignment

Supply JSON files declaring `schema: recomp-checkpoints-v1`, roles `reference`/`candidate`, matching `source_sha256`, `initial_state_sha256`, `isa`, and monotonically increasing `points` with `seq` and at least one shared observation (`pc`, `cycles`, `registers`, `memory`, `io`, `interrupts`, `device_state`). A mismatched hash or mismatched observation set is rejected.

```powershell
$r='C:\Projects\RecompDev-v0.4.0.32'; py -3 "$r\recomp.py" compare-checkpoints --reference 'C:\path\to\reference.json' --candidate 'C:\path\to\candidate.json' --out "$r\evidence\comparison-v0432.json"
```

## Qualification boundaries

- Windows verification on the owner's development system: **not yet observed for this release**.
- Authentic Sony/Mega Drive executable compilation using the new backend: **not yet observed**. Only author-created programs have been compiled and executed in release tests.
- Ridge Racer improved authentic function recovery: **not established** (previous v0.4.0.30 real-game benchmark unchanged at 14,222 instructions, 213 candidates, 81 barriers).
- Sonic authenticity: earlier owner-run M68000 static recovery increased 1,274 to 1,777 instruction candidates, 54 to 77 function candidates; these have **not** been proved executable or independently correct.
- MAME/CPU/console timing parity, genuinely verified playable commercial games, autonomous defect repair: **not established**.
- Support for a new game on an *already modelled ISA* has genuine reusable potential; support for a completely new ISA, OS or console needs an adapter and tests.

**Acceptance philosophy:** More capabilities are not correctness. Every claimed success is tagged at the level actually demonstrated: static candidate, compiled source-derived restricted code, deterministic native execution, independently verified CPU/hardware behaviour, or gameplay.
