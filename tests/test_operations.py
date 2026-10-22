"""Filesystem recovery tests use a disposable SQLite database and private evidence."""
import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from scripts.backup import create_backup
from scripts.common import operation_lock
from scripts.restore import restore_backup


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nava tests with spaces ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "source data"
        (self.data / "evidence" / "2026").mkdir(parents=True)
        self.original = b"Private evidence version one\x00\x01"
        (self.data / "evidence" / "2026" / "record.bin").write_bytes(self.original)
        (self.data / "secret.key").write_text("unit-test-secret-never-a-real-credential")
        # sqlite3's context manager commits/rolls back but does not close the
        # connection. Explicit closure is required before Windows file cleanup.
        with closing(sqlite3.connect(self.data / "nava.sqlite3")) as db, db:
            db.execute("CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT)")
            db.execute("INSERT INTO django_migrations (app) VALUES ('workspace')")
            db.execute("CREATE TABLE workspace_evidenceversion (id INTEGER PRIMARY KEY, file TEXT)")
            db.execute("INSERT INTO workspace_evidenceversion (file) VALUES ('2026/record.bin')")
        self.archive = self.root / "backup archive.zip"

    def test_backup_restore_preserves_database_evidence_secret_and_manifest(self):
        manifest = create_backup(self.data, self.archive)
        self.assertEqual(manifest["files"]["evidence/2026/record.bin"]["sha256"], hashlib.sha256(self.original).hexdigest())
        destination = self.root / "restored data"
        restored_manifest, old = restore_backup(self.archive, destination)
        self.assertIsNone(old)
        self.assertEqual(restored_manifest, manifest)
        self.assertEqual((destination / "evidence" / "2026" / "record.bin").read_bytes(), self.original)
        self.assertEqual((destination / "secret.key").read_bytes(), (self.data / "secret.key").read_bytes())
        with closing(sqlite3.connect(destination / "nava.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM workspace_evidenceversion").fetchone()[0], 1)

    def test_running_server_lock_refuses_backup_and_restore(self):
        create_backup(self.data, self.archive)
        with operation_lock(self.data):
            with self.assertRaisesRegex(RuntimeError, "running"):
                create_backup(self.data, self.root / "second.zip")
            with self.assertRaisesRegex(RuntimeError, "running"):
                restore_backup(self.archive, self.data, overwrite=True)

    def test_operation_lock_releases_after_failed_maintenance(self):
        with self.assertRaisesRegex(ValueError, "maintenance failed"):
            with operation_lock(self.data):
                raise ValueError("maintenance failed")
        with operation_lock(self.data):
            with self.assertRaisesRegex(RuntimeError, "running"):
                with operation_lock(self.data):
                    self.fail("A competing operation acquired the same lock")
        # A failed contender must not interfere with subsequent acquisition.
        with operation_lock(self.data):
            pass

    def test_overwrite_requires_explicit_flag_and_preserves_original(self):
        create_backup(self.data, self.archive)
        (self.data / "do-not-lose.txt").write_text("existing user content")
        with self.assertRaisesRegex(RuntimeError, "not empty"):
            restore_backup(self.archive, self.data)
        _, preserved = restore_backup(self.archive, self.data, overwrite=True)
        self.assertEqual((preserved / "do-not-lose.txt").read_text(), "existing user content")
        self.assertFalse((self.data / "do-not-lose.txt").exists())
        self.assertEqual((self.data / "evidence" / "2026" / "record.bin").read_bytes(), self.original)

    def test_rejects_tampered_evidence_before_creating_destination(self):
        create_backup(self.data, self.archive)
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(self.archive) as source, zipfile.ZipFile(tampered, "w") as out:
            for entry in source.infolist():
                contents = b"tampered" if entry.filename.endswith("record.bin") else source.read(entry.filename)
                out.writestr(entry, contents)
        destination = self.root / "should not exist"
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            restore_backup(tampered, destination)
        self.assertFalse(destination.exists())

    def test_rejects_path_traversal_and_extra_members(self):
        create_backup(self.data, self.archive)
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("../escaped.txt", "malicious")
        with self.assertRaisesRegex(RuntimeError, "manifest"):
            restore_backup(self.archive, self.root / "unsafe")
        self.assertFalse((self.root / "escaped.txt").exists())

    def test_backup_refuses_missing_evidence(self):
        (self.data / "evidence" / "2026" / "record.bin").unlink()
        with self.assertRaisesRegex(RuntimeError, "evidence file"):
            create_backup(self.data, self.archive)
        self.assertFalse(self.archive.exists())

    def test_backup_never_overwrites_or_recursively_includes_its_output(self):
        create_backup(self.data, self.archive)
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            create_backup(self.data, self.archive)
        with self.assertRaisesRegex(RuntimeError, "outside"):
            create_backup(self.data, self.data / "inside.zip")

    def test_rejects_duplicate_manifest_entries(self):
        create_backup(self.data, self.archive)
        with zipfile.ZipFile(self.archive, "a") as archive:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("manifest.json", "{}")
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            restore_backup(self.archive, self.root / "duplicates")
