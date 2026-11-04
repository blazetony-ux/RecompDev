# RecompDev v0.4.0.36 — Z80 correctness evidence / seven-ROM regression

## Purpose and limits

This release is a correction/diagnosis build derived from v0.4.0.35, not a claim that Shinobi, Alex Kidd, Bank Panic or the other Master System games now play correctly. No ROMs, game-specific offsets, emulator fallback, or MAME CPU traces are distributed. The shared CPU translation path is unchanged apart from emitting source-verified/unsupported-code coverage manifests.

## Engine changes

- Native SMS host: bounded ring of the last 256 translated Z80 transitions. The trace records logical and physical PC (with validity flags), before/after SP, a **RAM peek** of the stack word without triggering bus reads, mapper, interrupt count/enable flags, coarse opcode class, and hardware write counters. Each host frame also records PC, SP, IRQ and VDP/PSG/CRAM counter snapshots. This is an execution provenance hint, **not** an independent reference comparison or exact branch-taken classification. RAM stops retain the preceding transition.
- C++ generation: `emitted-offsets.json` and `unsupported-offsets.json` distinguish attested instruction bytes from successfully lowered/compiled dispatch entries. No ROM bytes are written to these manifests. A repeated stop at already-emitted code is classified differently from source-attested-but-not-emitted code; neither is misreported as a successful recovery.
- Continuous recovery v0436: explicit `BUILD_TIMEOUT`/`BUILD_FAILED` structured reports, configurable bounded compile time, up to 10 owner-selected recovery passes, and optional headless frame/audio capture. As before, all recovered instruction bytes are reverified against the owner ROM before translation/rebuild/reset/replay. `--capture-hardware` captures frame hashes and optional last-frame PPM/audio WAV locally; the campaign evidence ZIP excludes PPM/WAV and generated binaries.
- Conservative session triage: identifies candidate predecessor of a RAM PC and compares late hardware-counter activity across the bounded transition window. It **does not** infer the root cause from a CPU trace alone. Campaign cross-game observations are correlations, not causal proof.
- Seven-game campaign: discovery, independent Ghidra preparation, source-attested continuous recovery, and cross-game triage. Each game is isolated; missing games and failures do not abort the others.

## Windows installation / verification

Close the previous Workbench first. Every command here is a single line.

1. Extract:
`Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.36-Z80-Correctness-Campaign.zip" -DestinationPath 'C:\Projects' -Force`

2. Verify complete release:
`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.36\Verify-v0436.ps1'`

3. Launch Workbench:
`powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.36\Run-Workbench.ps1'`

4. In a separate PowerShell window, launch authentic ROM campaign (runs locally; may take a long time and compile many projects):
`py -3 'C:\Projects\RecompDev-v0.4.0.36\tools\Run-SMS-Campaign-v0436.py'`

The campaign expects `C:\Roms\MASTERSYSTEM` and migrates working catalogue from v0.4.0.35. The Shinobi filename defaults to `Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms`. If that exact file is missing, the runner accepts **one uniquely named** `Shinobi*.sms` file; if multiple exist it stops that game rather than guess. Others use the exact file names established in the owner's 2026-11-01 campaign.

The campaign prints `EVIDENCE_ZIP=...`. Upload **that ZIP**; it contains JSON diagnostics and logs but no original ROMs, native binaries, PPM/WAV captures or generated machine code. The campaign's return value is not proof of playable games. `BUILD_TIMEOUT` and `RECOVERY_BLOCKED` are actionable findings, not hardware parity results.

## Shinobi status

Shinobi is the **first** test in the campaign, with bounded recent CPU/mapper/interrupt/stack evidence plus captured frame hashes and audio metrics. The existing historical MAME/native comparison remains unaligned; `SHINOBI_MAME_CPU_ALIGNMENT=NOT_ESTABLISHED`. A first *causal* divergence cannot be claimed until a matching reset state and matched instruction/frame phases are independently established. The current release provides diagnostic prerequisites, not a playable Shinobi fix.

## Known limitations

- ROM-space source-attested static lowering only; RAM execution remains a safe explicit stop, not an invented RAM-code interpreter.
- Interrupt/VDP/PSG hardware implementation remains approximate. Frame hashes originate from the native host, not a MAME oracle.
- No game-specific semantics or automatically inferred CPU repair have been added. R-Type may still be blocked by an unsupported instruction or dispatch mapping; the report now distinguishes those cases.
- Full seven-game authentic-ROM acceptance and Windows owner acceptance are intentionally pending until the owner's campaign is returned.
