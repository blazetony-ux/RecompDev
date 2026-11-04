# RecompDev v0.4.0.6 — Shinobi Startup Loop & Hardware Trace

## Goal

The owner's real v0.4.0.5 Shinobi run successfully compiled and executed 50,000 steps after authenticating Ghidra recovery of bank 6. The stop was `STEP_BUDGET_REACHED`; its final PC trail alternated between Z80 `0x00AC` (`ADD HL,DE`) and `0x00AD` (`JR C,0x00AC`). There were 11 PSG writes and 24 I/O writes, **zero VRAM/CRAM writes**, and no independent gameplay/CPU parity evidence.

v0.4.0.6 adds **much larger bounded native execution and diagnostics**, not a claim that Shinobi is now playable.

## New functionality

- **500,000-step default** through Workbench, with 10k, 50k, 100k, 250k, 500k, 1m, 2m selections. Server and native process both enforce a 1–2,000,000 step range. The native process also has a ~25-second runtime watchdog and the Python orchestrator has a separate hard timeout.
- **Actual native CPU state checkpoints:** sampled at the beginning, at selected instruction counts, and at the end, including `PC`, `AF`, `BC`, `DE`, `HL`, `SP`, mapper and hardware write counters. No checkpoint *restore*: recompile still restarts at reset.
- **Physical ROM execution hotspots:** top eight executed physical ROM offsets with frequency, plus a conservative indicator for concentrated loop activity. It does **not** call loops infinite based solely on repeated PCs.
- **Hardware event diagnostics:** first VDP control/data write step, VDP port write and read counts, first PSG write step, and per-port write totals. VDP counts are **not** proof of an authentic image; no accurate frame scheduler, sprites, audio output or reference parity is implemented.
- **Visible Workbench diagnostics:** new CPU/hardware diagnostic section on the separate Native Execution page. Read-only report and step timeline still available.
- **Prior bank-6 evidence reuse:** the new SQLite catalogue snapshots v0.4.0.5 first. Its authenticated bank exports may be read from the original v0.4.0.5 evidence folder when that installation still exists. Only approved version-specific evidence directories are considered, and every candidate instruction hash is rechecked against the owner's original ROM; arbitrary DB paths are not trusted.
- **Long-loop regression fixture:** generated native C++ for an *independent synthetic* Z80 `ADD HL,DE` / `JR C` / `DJNZ` loop crosses 250,000 steps and exits. Register/PC checkpoints are compared with a separately implemented Z80 byte-level subset oracle. It is **not** complete Z80 parity and does not exercise the owner's commercial ROM.

The project remains a **whole-program native recompilation** effort. All game instruction execution in the test runner is generated compiled C++ with hard stops for unsupported code; the optional independent subset oracle is only a development test.

## Install (PowerShell)

Download `RecompDev-v0.4.0.6-Shinobi-Startup-Trace.zip` to your Downloads folder. Close any older Workbench on port 8777, then:

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.6-Shinobi-Startup-Trace.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.6\Run-Workbench.ps1'
```

Open `http://127.0.0.1:8777/execution`, select Shinobi and run the default **500,000** native-step attempt with recovery attempts set to 2. Larger step budgets (up to 2 million) are available but may hit the wall-clock watchdog before the step ceiling.

Old installations and original ROMs are not modified. The new `catalogue.v0406-working.sqlite` is created from the previous v0.4.0.5 working catalogue if present; bank export files continue to be read *in place* from the earlier installation, after source-byte verification. **Do not delete v0.4.0.5** if you want previously recovered bank-6 exports to be reused.

## Evidence to send back

After the run, inspect / upload:

- `C:\Projects\RecompDev-v0.4.0.6\evidence\native-pilot-v0406\jobs\<job-id>\pilot-report.json`
- Its `execution.log` (latest attempt) and `worker.log`.
- If it requests another unmapped bank, include `recovery\attempt-*\ghidra.log` for any failed recovery.

`pilot-report.json` contains `execution_diagnostics`, `recovery_attempts`, `trace.checkpoints`, `trace.hotspots`, first hardware event steps and the actual stop reason.

## Still missing

A proven reference Z80 execution of real Shinobi; accurate input/timing, VDP display/scrolling/sprites/frame scheduling, PSG audio synthesis, ROM banking corner cases, RAM code and interrupts; and full native game coverage. The test oracle only checks the carry-loop subset with synthetic source bytes. Reaching more native steps or writing VDP ports does not prove the screen or game works.
