#!/usr/bin/env python
"""Verify and restore a NAVA backup into a new data directory."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import zipfile

try:
    from .common import fail, operation_lock, private_permissions
    from .backup import FORMAT_VERSION, digest, verify_database
except ImportError:
    from common import fail, operation_lock, private_permissions
    from backup import FORMAT_VERSION, digest, verify_database

MAX_RESTORED_BYTES = 2 * 1024 * 1024 * 1024


def checked_name(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or name != path.as_posix():
        raise RuntimeError("The backup contains an unsafe archive path.")
    return name


def unpack_verified(backup: Path, staging: Path) -> dict:
    with zipfile.ZipFile(backup) as archive:
        infos = archive.infolist()
        names = [entry.filename for entry in infos]
        if len(names) != len(set(names)):
            raise RuntimeError("Duplicate archive entries are not allowed.")
        if sum(entry.file_size for entry in infos) > MAX_RESTORED_BYTES:
            raise RuntimeError("This backup exceeds the 2 GiB restore limit; use an administrator-reviewed recovery procedure.")
        if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > 10 * 1024 * 1024:
            raise RuntimeError("The backup manifest is missing or too large.")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "nava-backup" or manifest.get("version") != FORMAT_VERSION or not isinstance(manifest.get("files"), dict):
            raise RuntimeError("Unsupported backup format.")
        expected = {"manifest.json"} | {f"data/{checked_name(name)}" for name in manifest["files"]}
        if set(names) != expected or "nava.sqlite3" not in manifest["files"]:
            raise RuntimeError("Archive contents do not match the backup manifest.")
        for entry in infos:
            checked_name(entry.filename)
            if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1 or entry.is_dir():
                raise RuntimeError("Symbolic links, encrypted entries, and unexpected directories are not supported.")
        for name, expected_info in manifest["files"].items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(f"data/{name}") as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            private_permissions(target)
            if target.stat().st_size != expected_info["size"] or digest(target) != expected_info["sha256"]:
                raise RuntimeError("Backup checksum verification failed; nothing was restored.")
        verify_database(staging / "nava.sqlite3", staging)
    return manifest


def restore_backup(backup: Path, destination: Path, overwrite: bool = False) -> tuple[dict, Path | None]:
    if destination.is_symlink():
        raise RuntimeError("Restore destinations must not be symbolic links.")
    backup, destination = backup.resolve(), destination.resolve()
    if backup.is_relative_to(destination):
        raise RuntimeError("Use a regular destination outside the backup archive's location.")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise RuntimeError("Destination is not empty. Choose a new directory, or pass --overwrite to preserve and replace it explicitly.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    preserved = None
    with tempfile.TemporaryDirectory(prefix="nava-restore-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "verified"
        staging.mkdir()
        private_permissions(staging)
        manifest = unpack_verified(backup, staging)
        # The existing launcher must be stopped. Lock the current destination while preserving it.
        with operation_lock(destination):
            non_lock_files = [path for path in destination.iterdir() if path.name != "operation.lock"]
            if non_lock_files:
                if not overwrite:
                    raise RuntimeError("Destination became nonempty during verification; no files were replaced.")
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                preserved = destination.with_name(f"{destination.name}.before-restore-{stamp}")
                preserved.mkdir()
                private_permissions(preserved)
                for path in non_lock_files:
                    shutil.move(str(path), preserved / path.name)
            try:
                for path in staging.iterdir():
                    shutil.move(str(path), destination / path.name)
            except BaseException:
                # Original files remain in the named recovery directory if filesystem errors interrupt placement.
                raise RuntimeError(f"Restore placement failed. Preserved original directory: {preserved}")
        private_permissions(destination)
    return manifest, preserved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--to", type=Path, required=True, help="New data directory")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly preserve and replace an existing data directory")
    args = parser.parse_args()
    manifest, preserved = restore_backup(args.backup, args.to, args.overwrite)
    print(f"Verified {len(manifest['files'])} files and restored to {args.to.resolve()}.")
    if preserved:
        print(f"Previous data preserved at {preserved}.")
    print("Set NAVA_DATA_DIR to this directory and use the original application version before applying any updates.")
    if not manifest.get("includes_local_secret"):
        print("Restore the original NAVA_SECRET_KEY through your environment configuration before starting.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, sqlite3.Error, zipfile.BadZipFile, ValueError, KeyError) as exc:
        fail(str(exc))
