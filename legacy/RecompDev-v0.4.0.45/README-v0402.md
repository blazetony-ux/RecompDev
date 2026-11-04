# RecompDev v0.4.0.2 — Discovery from the Workbench

This is a **full, isolated continuation** of RecompDev v0.4.0.1. It retains the original function catalogue, Ghidra/recovery pipeline, C++ conversion code, autonomous discovery pipeline, asset preview gallery, three-page navigation, and existing evidence by copying the previous working SQLite database using the existing SQLite backup importer. It does **not** overwrite earlier installations or original ROMs.

## The new workflow (no PowerShell commands for individual ROMs)

1. Extract `RecompDev-v0.4.0.2-Workbench-Discovery-Controls.zip` to `C:\Projects`.
2. Double-click `C:\Projects\RecompDev-v0.4.0.2\Start-Workbench.cmd` to start the local server. The first launch creates a separate `catalogue.v0402-working.sqlite` by backing up the best available previous catalogue (preferring existing discovery evidence).
3. Browse to `http://127.0.0.1:8777/discovery`.
4. Under **Add ROMs and run discovery**, choose `C:\Roms`, open `MASTERSYSTEM`, select your Shinobi `.sms` file, then press **Add selected ROM & discover**.
5. The same panel can scan an entire folder, select analysis budget and file limit, retry explicitly failed jobs, stop a running job, and show worker output. The source, asset gallery, and backlog automatically refresh after completion.

The page browses filenames on the server's explicitly configured ROM roots. It **does not upload or serve ROM bytes**, take arbitrary commands, or access paths outside those roots. Requests are restricted to localhost, protected by origin and action token checks, and launched with fixed executable arguments (never shell=True).

### Configuring additional trusted ROM roots

The default root is `C:\Roms`. If the library is elsewhere, launch once using:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.2\Run-Workbench.ps1' -RomRoot 'D:\MyRoms'
```

This one-time setting controls which folders the local page is allowed to browse. For additional roots, supply a PowerShell string array using the `-RomRoot` parameter. Do not expose this server on a public network.

### PowerShell CLI fallback

`Run-v0402-Discover.ps1` is still available for scripted runs. It uses the **same** v0.4.0.2 working SQLite DB, so UI and CLI results stay in sync.

### What Master System support means today

`.sms` and `.gg` are now picked up during recursive directory discovery. The recogniser checks for `TMR SEGA` at the standard 8-bit header positions (0x1FF0, 0x3FF0, 0x7FF0). If found, it assigns `mastersystem` or `gamegear` and claims the 16-byte header structure; otherwise it assigns an explicit extension-only candidate status. No internal game title is inferred if the header does not provide one.

**Shinobi is only added to the discovery inventory and persistent tasks.** Z80 function decompilation, Master System asset extraction and native whole-game recompilation are not implemented in this navigation build. No full-function parity is implied.

### Diagnostics and evidence

New UI-launched jobs are saved separately under `evidence\discovery-v0402\jobs\<job-id>\` and include `worker.log` and, on success, `discovery-report.json`. Your existing Workbench stays on its own database copy and previous projects are untouched.

The new action API is intentionally narrow:

- GET `/api/discovery-control` — job state, configured roots, action token (same-origin only)
- GET `/api/discovery-library?folder=...` — bounded directory names/filenames within approved roots
- GET `/api/discovery-job` — current job status and bounded worker-log tail
- POST `/api/discovery-run` — run one fixed discovery worker on a selected file/folder
- POST `/api/discovery-cancel` — request stop of the current worker

The other Workbench pages remain **read-only** evidence browsers. Discovery writes only to the separate working SQLite DB and generated evidence directories.

## Regression scope

- Original v0.4.0.1 regression suite (74 tests).
- New browser-action, path-escape, CSRF, invalid parameter, end-to-end synthetic Master System import and deduplication tests (5 tests).
- No actual Windows testing of the new launcher is possible in this environment. The Windows end-to-end run must be validated on the user's PC.
