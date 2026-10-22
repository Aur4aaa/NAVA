#!/usr/bin/env python
"""Run NAVA with Waitress after checking the local installation."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from common import ROOT, data_directory, fail, operation_lock, python_executable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        fail("Port must be between 1 and 65535.")
    executable = python_executable()
    if not executable.is_file():
        fail("Virtual environment is missing. Run python scripts/setup.py first.")
    # On POSIX the virtualenv interpreter is a symlink to the base interpreter;
    # comparing resolved executable paths would incorrectly skip activation.
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        result = subprocess.run([str(executable), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=ROOT)
        raise SystemExit(result.returncode)
    directory = data_directory()
    if not (directory / "nava.sqlite3").is_file():
        fail("Database is missing. Run python scripts/setup.py first.")
    if not os.environ.get("NAVA_SECRET_KEY") and not (directory / "secret.key").is_file():
        fail("The local secret is missing. Restore the original secret or run setup for a new installation.")
    if not (ROOT / "staticfiles" / "staticfiles.json").is_file():
        fail("Static assets are missing. Run setup or manage.py collectstatic --noinput.")
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
    except OSError:
        fail(f"Port {args.port} is already in use. Stop the existing process or select --port.")
    for path in (directory, directory / "evidence"):
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        fail("Database migrations are pending. Stop the server, back up, and run setup.")
    from django.core.management import call_command
    call_command("check", verbosity=0)
    connection.close()
    from config.wsgi import application
    from waitress import serve
    with operation_lock(directory):
        print(f"NAVA listening on 127.0.0.1:{args.port}. Press Ctrl+C to stop.", flush=True)
        serve(application, host="127.0.0.1", port=args.port, threads=4, ident="NAVA", max_request_body_size=12 * 1024 * 1024)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("NAVA stopped.")
    except (RuntimeError, OSError, ImportError) as exc:
        fail(str(exc))
