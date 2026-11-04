# RecompDev v0.4.0.9 — Universal Instruction Recovery & Parity Foundation

**Purpose:** Strengthen a multi-game, multi-system recompilation workbench, **not** build a Shinobi-only native executable.

## Install (Windows PowerShell)

Close the previous Workbench, download `RecompDev-v0.4.0.9-Universal-Instruction-Recovery.zip` and run:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.9-Universal-Instruction-Recovery.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.9\Run-Workbench.ps1'
```

Open `http://127.0.0.1:8777/execution`, select a prepared Master System target, set a bounded budget and click **Autonomously recover, compile & trace native C++**. The v0.4.0.9 working catalogue is independent and preferentially imports from v0.4.0.8. **Keep your earlier installed evidence directories**, especially recovered bank data; all reused instruction hashes are checked against the owner's ROM.

## New architecture and actual capabilities

- **Exact instruction recovery:** `ghidra/ExportExactInstruction.java` exports at most 64 adjacent decoded instructions at the runtime stop PC, independently of Ghidra's Function database. The existing function exporter remains in use. Both evidence streams undergo physical-offset/source hash authentication before code generation.
- **Byte-level uncertainty screening:** `nativecore/instruction_evidence.py` inspects local ROM bytes, records the entry byte and a bounded repeated-byte run, and blocks automatic translation when a long run of `0xFF` indicates *suspected* padding. Suspicion does not prove the interrupt is invalid. ROM data are not distributed.
- **Better evidence on refusal:** Each recovery attempt now writes `entry-diagnostics.json` and, if Ghidra runs, `exact-entry.json` and `ghidra.log`. Workbench shows the specific blocker and byte classification.
- **Independent sampled checkpoint comparison:** `nativecore/parity.py` compares native checkpoints against *separately supplied* reference evidence bound to the same source SHA-256. It reports first mismatches and missing checkpoints; no reference emulator is bundled or run automatically.
- **Generic capability contracts remain intact:** Master System/Z80 has experimental C++ execution. Mega Drive/68000 and PS-X EXE/MIPS have preparation and capability reporting, **not** integrated native execution. The systems/mastersystem hardware runtime remains partial and cycle-inaccurate.
- **No ROM-specific code:** no game titles, Shinobi addresses, or exception patches in recovery; physical bank/entrypoint mapping is defined by the console adapter.

## Manual reference checkpoint comparison (optional)

```powershell
cd C:\Projects\RecompDev-v0.4.0.9
py -3 -m nativecore.parity --reference C:\Path\To\independently-collected-reference.json --candidate C:\Path\To\pilot-report.json --output C:\Path\To\parity-report.json
```

Reference evidence schema (`source_sha256` must equal the tested ROM's SHA-256):

```json
{"schema":"recomp-independent-checkpoint-reference-v1","source_sha256":"<actual 64-character SHA-256>","independent_source":"<named independent reference capture>","checkpoints":[{"step":1000,"pc":56,"af":0,"bc":0,"de":0,"hl":0,"sp":0}]}
```

This is a format example, **not** a valid completed reference capture. A matching sampled checkpoint does not prove CPU, hardware, timing, video or whole-game parity. Step alignment must be established independently.

## Test scope and limitations

- Reusable exact-address recovery was tested with a simulated Ghidra export containing **no functions**; a two-byte source-attested instruction was correctly added and verified.
- A deliberately forged instruction hash was rejected.
- Repeated `0xFF` at a vector was classified suspicious and refused; diagnostic evidence was saved.
- Independent Z80 cartridge native-IRQ integration tests, bank recovery, preparation, Workbench and bridge tests passed.
- The exact new Ghidra Java script has **not yet been run on your Windows Ghidra 12.2**. Synthetic Ghidra hand-off tests cannot prove its real output.
- We cannot infer the bytes at Shinobi's `0x0038` without the original ROM on your machine. The next real Windows test will determine whether code exists there or reference IRQ investigation is necessary.
- No independent reference emulator validation, native 68000/MIPS run, playable Shinobi, or accurate rendered game screen has been demonstrated.

## Feedback from the first Windows run

Upload `pilot-report.json`, `worker.log`, `execution.log`, `recovery/attempt-*/entry-diagnostics.json`, `recovery/attempt-*/exact-entry.json` (if created), and the corresponding `ghidra.log` (if Ghidra executed) from `evidence/native-pilot-v0409/jobs/<job-id>/`. If the diagnostic reports suspected padding, **do not force compilation**; investigate the correct interrupt mode and hardware event using independent reference execution.
