# Next build handoff from v0.4.0.2

The new Workbench can add and investigate a game without PowerShell. `Shinobi.sms` can now be inventoried as a Mega Drive-adjacent Sega 8-bit target, but is NOT in the executable-code graph catalogue. That requires a Z80 graph/disassembler adapter with explicit mapping and bank handling. For the next substantive release: add Master System Z80 code-region and reset/interrupt discovery; real tile and palette extraction; asset/code reference linking; and whole-program native-build readiness for a small source-known Mega Drive homebrew. Keep versioned database backups and safe local-only action APIs.

The `discovery/workbench_jobs.py` controller is the only write endpoint. Do not allow arbitrary command execution or arbitrary local path scanning. Keep ROM bytes on disk and never send them to the browser.
