# Workbench — local read-only SQLite catalogue browser

**Scope:** `developer-tool`. **Component:** `workbench` in `workspace/components.json`. **Initial version:** 0.1.0. Independent Python web service with no third-party libraries and no dependency on the compiled RecompDev controller.

## Windows launch

```powershell
& "C:\Projects\RecompDev\tools\Start-Workbench.ps1"
```

The script starts Python's built-in HTTP server at `http://127.0.0.1:8765`, prints a one-time access URL containing a random token, and opens a browser unless `-NoBrowser` is specified. Stop with `Ctrl+C`. To use a different database or port: `-Database 'C:\path\to\catalogue.sqlite' -Port 8777`.

The default database is `C:\Projects\RecompDev-Data\catalogue.sqlite`. **Workbench never copies, alters or migrates this database.** The service opens SQLite in `mode=ro` with `query_only=ON`; browsers can only list tables, inspect column types, paginate rows and filter by one vetted column. HTTP POST/PUT/DELETE are rejected. No arbitrary SQL endpoint is present. It binds only to loopback, requires a per-start token, HTML-escapes data and caps page sizes.

## API and evidence

Read-only JSON endpoints `/api/tables` and `/api/table/<encoded table name>` use the same token. Server logs live under the current workspace version, initially `C:\Projects\RecompDev-Evidence\v0.4.7\workbench`, not the Git source tree. Database filenames and row content can contain private owner-local information; keep the token URL and screenshots local.

Run the service tests with `python -B -m unittest workbench.tests.test_server -v`. It is intentionally a catalogue **viewer** at this stage. It does not have task queues, run actions, write transactions, a multi-user account system or an externally exposed service. Those capabilities require independent design and tests.
