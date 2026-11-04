# RecompDev v0.4.2 — Automatic evidence upload package (Hotfix 2)

This is a non-destructive update to the **compiled RecompDev.exe workflow**. It
uses the existing legacy v0.4.0.45 analysis and native recovery services,
without changing their files, the Master System runtime, the Z80 translator,
or production SQLite catalogue.

The compiled `RecompDev.exe` command and arguments remain unchanged. Its Python
service adapter now creates `<run-id>-evidence.zip` **beside** each evidence
folder at the end of a `run-rom` workflow, whether the operation finishes or
reports a recovery blocker. `run-campaign` and `compare-discovery` through the
Python CLI are also covered. The result JSON gains `evidence_bundle`, and
stderr prints `RECOMPDEV_EVIDENCE_ZIP=<absolute path>`.

The ZIP contains discovery/preparation/recovery reports, Ghidra exports,
per-round logs, runtime sessions, frame PPMs, WAVs, isolated working SQLite
catalogues, source-verified code evidence, an integrity manifest, and named
hardware-state dumps when present. Original ROM/disc files, DLLs, EXEs,
compiled native-project/build directories, unknown `.bin` files, and source
code generated for builds are not included. Source files and generated
compiler outputs remain in the **original** evidence folder and can be
revisited if the condensed package is insufficient.

The ZIP is never overwritten. Every included file is SHA-256 listed in
`bundle-manifest.json`. Omitted paths and reasons are listed there too.
Review report contents before upload: they may contain local file paths and
working catalogue information. An evidence package is **not** a native-game
parity assertion.

To apply to Windows v0.4.2 after Controller Hotfix 1, download and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Downloads\Repair-RecompDev-v0.4.2-AutoEvidence.ps1"
```

The installer backs up only affected files, checks known source hashes,
reconfigures CMake and runs the existing 34 tests plus one new evidence-bundle
test. It does not require a full reinstall, and does not change the compiled
controller's C++ implementation. Its Windows verification must be performed
on the owner machine. The source package was tested on Linux.
