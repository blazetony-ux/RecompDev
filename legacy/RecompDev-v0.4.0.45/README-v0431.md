# RecompDev v0.4.0.31 — Authenticated Native History Repair

This is a separate release from v0.4.0.30. It fixes a reproducible Workbench API crash when an imported discovery source ID is not a complete SHA-256 value.

**Root cause:** `platform424.evidence.history()` requires the original binary's 64-digit source SHA, but Workbench used `discovery_sources.source_id` without checking its format, and omitted targets registered only in the static graph. A single unsupported source ID crashed `/api/unified-evidence` and made `/api/overview` silently discard its native history.

**Fix:** source-history inputs are now reconciled from (a) valid SHA-256 `discovery_sources` rows and (b) authenticated `targets.source_sha256` rows, deduplicated by the full hash. Other source IDs are not guessed or rehashed: they are skipped with explicit `identity_issues` / `native_history_issues` fields. A bad record cannot suppress other games' evidence. Source-hash and event-stream checks in the existing history reader remain unchanged.

**Expected behavior:** when the existing v0.4.0.29 original Shinobi campaign directory is present beside the new install, `/api/unified-evidence` and `/api/overview` should display it under the registered Shinobi SHA-256 identity. Native execution steps and static graph-function counts remain separate; this does not establish independent gameplay or MAME correctness.

The conservative M68000/MIPS static recovery and all native Z80/null-host code from v0.4.0.30 are retained. No commercial games or BIOS files are bundled.

## Windows instructions (PowerShell)

Extract the release ZIP into `C:\Projects`. Stop the old Workbench process first so port 8777 is available.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.31\Verify-v0431.ps1'
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.31\Run-Workbench.ps1'
```

In another PowerShell window:

```powershell
$u=Invoke-RestMethod 'http://127.0.0.1:8777/api/unified-evidence'; $u.data.targets | Where-Object {$_.source_id -eq 'dac4f1dcb41193cb42a96950444a87c5f2952ea66474c59a38c07b10ac411e47'} | ConvertTo-Json -Depth 8
```

The `identity_issues` field is intentionally visible for legacy catalogue IDs not backed by a full SHA-256. They are **not** assigned to any ROM without authenticated evidence. If Shinobi's real job directory was moved out of the numbered installation hierarchy, the history will be empty until the original evidence root is restored; the game need not be rerun.
