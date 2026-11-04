# RecompDev v0.4.0.40 — Autonomous Recovery & Extended Native Execution

## Implemented in this build

- **Windows host-stack policy:** both generated Windows native targets reserve 8 MiB through target-specific MSVC/MinGW linker options. The original Sonic SMS test demonstrated a stack-related Windows host failure, not proof that this is a sufficient reserve for every generated program.
- **Explicit native process failure classification:** nonzero Windows process exits retain signed and unsigned exit codes, including `0xC00000FD` stack overflow. Compiler success and native runtime success remain different statuses.
- **Bounded progress-aware source-verified recovery:** maximum 24 allowed passes; default 12 in the owner seven-game campaign; source SHA, mapper state, physical bank and original-byte provenance remain verified. A repeated earlier stop following a rebuild is diagnosed as no execution progress. **This does not invent missing game code.**
- **Staged native replay:** 120 → 300 → 600 (or optionally 1,800) frame checkpoints, only when the earlier checkpoint reaches its frame budget. Every stage reruns the unchanged original cartridge with the same input events and a proportionate instruction allowance, capped at 20 million. A later missing-code stop re-enters the attested recovery path.
- **Incremental generated-file updates:** unchanged C++ and device source files retain their timestamp across recovery attempts, letting CMake avoid rebuilding unaffected translation units. Changed translated instructions still rebuild.
- **Central SQLite catalogue** remains outside versioned installations: `C:\Projects\RecompDev-Data\catalogue.sqlite`.
- **Campaign evidence:** new v0439 source-identity-matched baseline, frame checkpoint records, and explicit **budget mismatch** reporting (longer runs must not be mislabelled directly comparable to 120-frame historical runs).
- **Native framebuffer viewer** refreshed for v0440 campaigns, with SHA-verified generated-executable provenance. No emulator CPU fallback.

## Boundaries and remaining proof requirements

- Full Windows seven-game acceptance, fresh Windows linker result, and real-game frame-accuracy comparison with MAME have not been established by local synthetic tests.
- No new VDP/PSG behavioral correction is claimed: the previous nonblack but inaccurate graphics and silent commercial-game WAVs still require independent hardware parity investigation.
- Recovery attempts can become expensive; advanced operators can lower budgets with `--frames 120 --max-recoveries 6` or raise observation to 1,800 frames using `--extended`. The campaign remains strictly bounded.
- Partial or full frame-budget completion is **not gameplay equivalence**. All recovered instructions continue to require ROM source attestation.

## Windows commands

```powershell
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.40-Autonomous-Recovery-Extended-Native.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.40\Verify-v0440.ps1'
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.40\Run-Workbench.ps1'
py -3 'C:\Projects\RecompDev-v0.4.0.40\tools\Run-SMS-Campaign-v0440.py'
```

The campaign prints `EVIDENCE_ZIP=...` when complete. The ZIP intentionally excludes original ROMs, native binaries and full generated source.
