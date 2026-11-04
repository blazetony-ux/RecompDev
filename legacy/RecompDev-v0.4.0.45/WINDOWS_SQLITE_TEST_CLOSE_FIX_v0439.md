# v0.4.0.39 — Windows SQLite test cleanup correction

## Defect observed in owner verification

The test `test_bootstrap_once_then_share_across_versioned_installations` held two SQLite destination connections open while `tempfile.TemporaryDirectory` attempted to remove the test folder. Windows raised `PermissionError: [WinError 32]` for its temporary `RecompDev-Data/catalogue.sqlite`. Python SQLite connection context managers do **not** close connections at `__exit__`; they only manage transactions.

## Correction

Both connection contexts in `tests/test_shared_catalogue_v0439.py` now use `contextlib.closing(sqlite3.connect(destination))`. The shared-catalogue runtime and importer already explicitly closed their own SQLite connections. There is no new database migration, seed import, catalogue reset, or change to catalogue storage. Existing `C:\Projects\RecompDev-Data\catalogue.sqlite` must be retained.

## Local acceptance

- 5 shared-catalogue regression tests passed.
- 18 other focused regressions passed, including compiled conditional control and right-shift checks.
- 15 bridge tests passed with one skipped.
- Compiled synthetic framebuffer and PCM verification passed.
- Repacked archive verified file-by-file against a refreshed SHA-256 manifest.

## Limits

Windows file locking must be rechecked on the user's system; the full repository suite and seven-game campaign were not repeated for this two-line test fix. Authentic gameplay parity remains unestablished.
