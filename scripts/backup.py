#!/usr/bin/env python
"""Make a verified portable backup while the managed NAVA server is stopped."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile

try:
    from .common import data_directory, fail, operation_lock, private_permissions
except ImportError:
    from common import data_directory, fail, operation_lock, private_permissions

FORMAT_VERSION = 1


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify_database(path: Path, data_root: Path | None = None) -> None:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise RuntimeError("SQLite integrity verification failed.")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "django_migrations" not in tables:
            raise RuntimeError("The database is not an initialized NAVA database.")
        if data_root and "workspace_evidenceversion" in tables:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(workspace_evidenceversion)")}
            if "file" in columns:
                for (name,) in connection.execute("SELECT file FROM workspace_evidenceversion WHERE file <> ''"):
                    target = (data_root / "evidence" / name).resolve()
                    if not target.is_relative_to((data_root / "evidence").resolve()) or not target.is_file():
                        raise RuntimeError("An evidence file referenced by the database is missing or unsafe.")


def create_backup(directory: Path, output: Path) -> dict:
    directory, output = directory.resolve(), output.resolve()
    if output.is_relative_to(directory):
        raise RuntimeError("Choose a backup destination outside the application data directory.")
    if output.exists():
        raise RuntimeError("The output file already exists; choose a new backup filename.")
    if not (directory / "nava.sqlite3").is_file():
        raise RuntimeError("No initialized database exists at the selected data directory.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with operation_lock(directory), tempfile.TemporaryDirectory(prefix="nava-backup-") as temporary:
        snapshot = Path(temporary) / "nava.sqlite3"
        with closing(sqlite3.connect((directory / "nava.sqlite3").as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        verify_database(snapshot, directory)
        files = {"nava.sqlite3": snapshot}
        excluded = {"nava.sqlite3", "nava.sqlite3-wal", "nava.sqlite3-shm", "nava.sqlite3-journal", "operation.lock"}
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise RuntimeError("Data directories containing symbolic links cannot be backed up safely.")
            if path.is_file() and path.relative_to(directory).as_posix() not in excluded:
                files[path.relative_to(directory).as_posix()] = path
        manifest = {
            "format": "nava-backup",
            "version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": {name: {"sha256": digest(path), "size": path.stat().st_size} for name, path in sorted(files.items())},
            "includes_local_secret": "secret.key" in files,
            "configuration": {name: os.environ.get(name, default) for name, default in {
                "NAVA_APP_NAME": "NAVA", "NAVA_TIME_ZONE": "Asia/Kuala_Lumpur", "NAVA_ALLOWED_HOSTS": "127.0.0.1,localhost", "NAVA_DEBUG": "0", "NAVA_HTTPS": "0"
            }.items()},
            "external_configuration": ["NAVA_SECRET_KEY (if supplied by environment)", "NAVA_APP_NAME", "NAVA_TIME_ZONE", "NAVA_ALLOWED_HOSTS", "NAVA_HTTPS"],
        }
        try:
            with output.open("xb") as stream:
                private_permissions(output)
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("manifest.json", json.dumps(manifest, indent=2))
                    for name, path in sorted(files.items()):
                        archive.write(path, f"data/{name}")
            # Verify every archived file against the manifest, not only the archive CRC.
            with zipfile.ZipFile(output) as archive:
                for name, info in manifest["files"].items():
                    with archive.open(f"data/{name}") as member:
                        check = hashlib.file_digest(member, "sha256").hexdigest()
                    if check != info["sha256"]:
                        raise RuntimeError("Backup verification failed; source files changed during the backup.")
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New ZIP file outside the data directory")
    parser.add_argument("--data-dir", type=Path, default=data_directory())
    args = parser.parse_args()
    manifest = create_backup(args.data_dir, args.output)
    print(f"Verified backup created: {args.output.resolve()} ({len(manifest['files'])} files).")
    print("Protect this archive: it contains private evidence and may include the local application secret.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        fail(str(exc))
