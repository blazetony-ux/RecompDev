# RecompDev v0.4.0.26 — Windows Verification & Null Host Correctness

This is a distinct, versioned full release. It supersedes v0.4.0.25 and both v0.4.0.25 hotfix overlays. No copyrighted game assets, generated ROM-derived code or executable binaries are included.

## Fixes from owner Windows verification

1. Native generated application's `--mode HEADLESS_AUTONOMOUS` now **rejects** `--video window`, `--audio speaker`, and `--input live`, regardless of argument order, rather than incorrectly succeeding. Discard-only video and audio remain completely optional: guest VDP and PSG state still advance normally.
2. Native campaign and test fixture SQLite connections are explicitly closed before teardown. `sqlite3.Connection`'s ordinary context manager does not close Windows file handles. Test-side update also commits changes before closing; on Windows the fixture attempts to unlink the database as a lock check.
3. Executable selection always prefers actual compiled executable products, not Visual Studio `.vcxproj` or metadata files (carried forward from the previous hotfix).
4. Version, CMake-generated project metadata, Workbench display, working catalogue filename, and complete release gate are all **v0.4.0.26**. Workbench imports a prior `v0.4.0.25` catalogue without modifying it.

## Owner installation

```
Expand-Archive "$env:USERPROFILE\Downloads\RecompDev-v0.4.0.26-Windows-Verification-Release.zip" -DestinationPath 'C:\Projects' -Force
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.26\Verify-v0426.ps1'
powershell -NoProfile -ExecutionPolicy Bypass -File 'C:\Projects\RecompDev-v0.4.0.26\Run-Workbench.ps1'
```

## Integrated authentic Shinobi campaign (only after Windows verification succeeds)

Run the Workbench once to import the catalogue; then stop it with Ctrl+C. Command (one PowerShell line):

```
$r='C:\Projects\RecompDev-v0.4.0.26'; py -3 "$r\tools\Run-Integrated-Native.py" --db "$r\catalogue.v0426-working.sqlite" --source-id 'dac4f1dcb41193cb42a96950444a87c5f2952ea66474c59a38c07b10ac411e47' --rom-root 'C:\Roms' --output-root "$r\evidence\integrated-native-v0426\jobs" --steps 500000 --frames 120 --recoveries 2 --mode HEADLESS_AUTONOMOUS
```

This command may stop on an untranslated-code boundary. It does not imply MAME parity, validated CPU semantics, hardware timing or playable gameplay.

## Verification claims

The compiled and integration tests use **author-created synthetic ROMs**. The Windows MSVC test has **not yet run on the owner's machine**. Actual parity with authentic Master System hardware and Shinobi gameplay is not established.
