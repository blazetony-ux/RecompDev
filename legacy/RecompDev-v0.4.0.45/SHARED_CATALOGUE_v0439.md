# RecompDev v0.4.0.39 central SQLite catalogue correction

From this revision, all new RecompDev releases should use a single persistent
`C:\Projects\RecompDev-Data\catalogue.sqlite` database.  The code and
packaged read-only seed remain in versioned `RecompDev-v...` directories.

- On first use, the Workbench, seven-game campaign, or main CLI searches
  legacy working catalogues, validates SQLite integrity and basic RecompDev
  tables, then makes **one** snapshot into the persistent directory.
- Evidence scoring selects the most complete single source. This is **not**
  a merge of different legacy catalogues. The chosen source and all
  candidates are recorded in `catalogue-sources-reviewed.json`. Old files
  are left untouched for follow-up imports/archiving when needed.
- Later runs use the central DB directly. The Workbench does not need to
  start before a campaign; a new software ZIP doesn't need to copy the DB.
- Override globally using `RECOMPDEV_CATALOGUE` or `RECOMPDEV_DATA_DIR`.
  Workbench's explicit `-Database` parameter remains supported.
- SQLite WAL mode is enabled by the existing backup importer for the
  first snapshot; all engines use normal SQLite transactions.
- Before a schema migration, take a verified SQLite backup and validate
  compatibility; regular backup is also advisable for failure recovery.
- Do not overwrite/delete the central database when extracting a release.
- The previous v0.4.0.39 release's campaign required a missing per-version
  working DB; this revision fixes that blocker, without altering game code.

## Runtime

`py -3 C:\Projects\RecompDev-v0.4.0.39\tools\Init-Shared-Catalogue-v0439.py`

`py -3 C:\Projects\RecompDev-v0.4.0.39\tools\Run-SMS-Campaign-v0439.py`
