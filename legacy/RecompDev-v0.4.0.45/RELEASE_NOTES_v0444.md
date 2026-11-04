# RecompDev v0.4.0.44 — Windows SQLite lifecycle and release-verification hardening

This is a newly numbered, full distribution, not a reissue of 0.4.0.43.

## Confirmed regression addressed

The 0.4.0.43 coverage-tampering tests used `with sqlite3.connect(...)`, which does
not close the database handle on exit. Windows therefore prevented cleanup of the
temporary `verified-coverage-v0443.sqlite` file, causing two test failures.
Both transactions now use `with closing(sqlite3.connect(...)) as con, con:`.

All six maintained versioned recovery CLI scripts also now explicitly close their
read-only catalogue connection. The new SQLite lifecycle preflight scans the entire
shipped Python source and test tree and rejects direct `sqlite3.connect` context
managers before expensive compiled tests run.

The new regression includes a tracked-connection fixture that catches unclosed
SQLite handles on Linux, instead of relying on Windows-only file deletion errors.

## Preserved functionality

0.4.0.43 verified-coverage cache format and name, synthetic PSG improvements,
frame timeline, native Start/Pause controller replay, Win32 stack reserve,
Workbench and existing evidence are preserved. **No schema migration or data
copying is performed.** The cache intentionally remains at
`RecompDev-Data/verified-coverage-v0443.sqlite` so previously recovered work
survives this software update.

## Release qualification

The tests must pass with the actual distributed archive. The Windows-verification
log is still required to confirm platform-specific behaviour. Authentic-game
parity, playable R-Type and commercial-game audio remain unproven.
