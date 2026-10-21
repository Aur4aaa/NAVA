# Operating NAVA

## Deployment boundary

The supported initial operating pattern is one organization on one computer, using a local browser. `scripts/start.py` always binds Waitress to `127.0.0.1`. Authentication, CSRF checks, record permissions, and authenticated evidence downloads apply locally as well as remotely.

Windows 11 is the intended initial platform; automated checks in this delivery ran under Linux with Python 3.12.14. Windows-specific file locking and launch behavior require validation on the target machine before operational adoption. Do not represent these commands as Windows-tested.

For a shared-network deployment, complete a separate hardening task: HTTPS reverse proxy, trusted host configuration, secure cookies, restricted filesystem/service account, operating-system patching, a tested backup schedule, review of proxy headers, capacity testing, and shared database configuration. The provided launcher deliberately does not expose a network bind flag. PostgreSQL migration is described in [architecture](architecture.md); it is not configured by the local setup.

## Installation and first accounts

From the project root:

```powershell
py -3.12 scripts/setup.py
```

Setup is safe to repeat: the virtual environment and existing secret are reused, migrations apply only pending changes, catalog/role commands are idempotent, and static assets are refreshed. No business demo is loaded by setup. Noninteractive setup skips the administrator prompt; use `--no-admin` to make that explicit. Use `--skip-install` only when the pinned dependencies are already installed.

Create named users through the provided account-management workflow or `manage.py createsuperuser` for the initial administrator. Avoid shared accounts. Assign business roles explicitly with `manage.py assign_role --username NAME --role ROLE`; role names containing spaces must be quoted. A superuser alone is not an authorized business approver.

The Settings page creates named accounts with explicit role presets. The `assign_role` command adds roles and preserves existing assignments; full existing-account lifecycle and arbitrary policy editing are later refinements. Passwords use Django password hashing and validation. The initial setup never prints a generated login password or stores a fixed demo credential. Failed logins are recorded without credentials; a temporary per-address throttle limits repeated failures in the local server process. Use `manage.py changepassword NAME` to reset a local user's password.

## Start, stop, and restart

```powershell
py -3.12 scripts/start.py
```

The launcher uses the project virtual environment even if invoked with a system Python. It checks that the database and application secret exist, static assets were collected, data/evidence directories are writable, migrations are current, Django system checks pass, and the chosen port is available.

Use `--port 8001` for a different local port. Stop with Ctrl+C in the launch terminal. Closing the computer or terminating the process stops the service; open sessions and processes are not a backup. Restart with the same command and environment variables. An unattended Windows service wrapper and automated startup are deferred.

The launcher holds an operating-system advisory lock in `NAVA_DATA_DIR/operation.lock`. Setup, backup, and restore use the same lock and refuse to proceed while the managed server runs. The lock is released when the process exits, so a leftover lock file is not evidence that the server is still running. Do not delete the lock file to bypass a live lock. This coordination covers the provided launcher and scripts; stop other Django shells, development servers, scheduled jobs, and manual database writers before maintenance.

## Configuration and secrets

Configuration is read from environment variables. `.env.example` is documentation only; copying it to `.env` does not load it. Set PowerShell variables in the same session before running setup or start, or configure them in a future operating-system service definition.

| Variable | Default | Purpose |
|---|---|---|
| `NAVA_DATA_DIR` | Project `.runtime` | SQLite, private evidence, local secret, maintenance lock |
| `NAVA_APP_NAME` | `NAVA` | Display name |
| `NAVA_TIME_ZONE` | `Asia/Kuala_Lumpur` | Initial/default timezone; the organization timezone saved in Settings controls request display; timestamps remain timezone-aware |
| `NAVA_ALLOWED_HOSTS` | `127.0.0.1,localhost` for documented local usage | Comma-separated accepted HTTP hosts |
| `NAVA_SECRET_KEY` | Private generated `secret.key` | Optional externally managed Django secret |
| `NAVA_DEBUG` | `0` | Keep disabled in normal use |
| `NAVA_HTTPS` | `0` | Secure-cookie and redirect configuration for a deliberately configured HTTPS deployment |

Never commit the data directory, application secret, passwords, or evidence. Windows account and folder ACLs remain necessary; Unix file mode restrictions do not translate into a full Windows ACL management system. A database or local machine administrator can modify storage. Application audit history is append-only through ordinary application operations, not a tamper-proof ledger.

## Backup

1. Stop the managed server and all other writers.
2. Choose a protected location outside the data directory.
3. Run:

```powershell
py -3.12 scripts/backup.py "C:\Backups\nava-2026-10-21.zip"
```

The command uses SQLite's backup API, checks database integrity and referenced evidence files, and archives the snapshot together with private files and the local secret when present. A manifest contains file sizes and SHA-256 hashes, generation time, safe configuration values, and external configuration requirements. Every archived file is read back and checked. A destination filename is never overwritten.

The manifest hashes detect byte differences; they are not signatures and do not prove the archive's authenticity. Keep archives confidential and use trusted storage. Archives are not encrypted by the script. If `NAVA_SECRET_KEY` comes from an external environment rather than `secret.key`, preserve it securely through your secret-management process; the script does not print or export it. Non-secret configuration values are recorded under `configuration` in `manifest.json`.

Use `--data-dir "C:\Path\To\Data"` to back up a different instance. Backup files inside the data directory and symbolic links in the data tree are rejected. The backup has no automatic retention or scheduling; establish and test a suitable local procedure.

## Restore and verify

Keep the original application version available. Restore to a new folder first:

```powershell
py -3.12 scripts/restore.py "C:\Backups\nava-2026-10-21.zip" --to "C:\Users\YourName\NAVA Restored Data"
$env:NAVA_DATA_DIR = "C:\Users\YourName\NAVA Restored Data"
py -3.12 scripts/start.py
```

Restore validates the archive layout, duplicate entries, unsupported entries, manifest hashes/sizes, SQLite integrity, and evidence references before placing files. It rejects absolute/traversing paths and symbolic links. The current safety limit is 2 GiB uncompressed content; larger installations need a reviewed recovery process.

An existing nonempty destination requires `--overwrite`. This explicit flag preserves the existing content beside the destination in a uniquely named `.before-restore-<timestamp>` directory before replacement. Keep that directory until you have verified the restored installation. If replacement encounters a filesystem error, the preserved original remains available; the script reports its location.

Reapply non-secret configuration recorded in the manifest and, when applicable, the externally managed secret. Sign in, open a representative scope and risk, inspect their approved histories, download evidence and compare its checksum, and confirm an audit package still resolves its frozen versions. The automated recovery tests cover file and database roundtrips; this human check confirms the restored organization is the intended one. Keep the original backup unchanged.

## Update

1. Record the current application revision and dependency versions.
2. Stop all writers and make a verified backup.
3. Preserve locally modified source files before installing the new reviewed application revision.
4. Run `python scripts/setup.py --no-admin` to refresh dependencies, migrate, and collect assets.
5. Run `manage.py check` and the relevant tests, then restart and inspect representative records.

For rollback, restore the matching prior code and backup together. Do not assume a migrated database is compatible with older application code. Framework catalog updates must create new catalog versions rather than rewriting historical organizational records.

## Troubleshooting

| Symptom | Action |
|---|---|
| Python or `py` is unavailable | Install Python 3.12 for the current user; reopen PowerShell and run `py -3.12 --version`. Administrative installation is not required by NAVA. |
| Dependency download fails | Verify network access to the configured package index, certificate trust, and the pinned versions. Do not disable TLS or package verification. Rerun setup after correcting the cause. |
| `ModuleNotFoundError` | Run the `.venv` Python, or rerun setup without `--skip-install`. Avoid mixing system and project packages. |
| Missing secret/database/static assets | Check `NAVA_DATA_DIR` and run setup for a new installation. For an existing instance, restore missing data or the original secret rather than silently replacing it. |
| Pending or failed migration | Stop the server; back up; inspect the migration error. Resolve the schema/data issue before rerunning setup. Do not delete migration history to force success. |
| SQLite database locked | Stop additional writers and avoid concurrent maintenance commands. The application waits briefly for normal writes; sustained errors require investigating overlapping processes. |
| Port already in use | Stop the existing local process or use `python scripts/start.py --port 8001`. Do not kill unrelated services. |
| Permission denied writing data/evidence | Confirm the launching OS account owns the selected data directory and has free disk space. Avoid cloud-synchronized folders and read-only installation paths. |
| HTTP 500 | Inspect the server terminal/log entry and diagnostic identifier if shown; preserve the request time and operation. Keep `NAVA_DEBUG=0` during normal use and do not share full sensitive data or secrets in reports. |
| Login works but business records are unavailable | Check explicit business role membership and record classification/sharing. Superuser status does not grant business approval authority. |
| Backup/restore says NAVA is running | Stop the managed server/maintenance process. A stale lock file itself is harmless; operating-system locks release on process exit. |

Uploads are private and authenticated, but malware scanning is not integrated. Do not interpret a stored checksum or successful upload as a malware scan, authenticity check, or effectiveness conclusion.
