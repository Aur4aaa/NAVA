#!/usr/bin/env python
"""Create or refresh a local installation without embedding credentials."""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import venv

from common import ROOT, data_directory, fail, operation_lock, private_permissions, python_executable, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-install", action="store_true", help="Use dependencies already installed in .venv")
    parser.add_argument("--no-admin", action="store_true", help="Do not prompt for a first administrator")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        fail("Python 3.12 or newer is required; Python 3.12.14 is the tested runtime.")
    executable = python_executable()
    if not executable.is_file():
        print("Creating the project virtual environment...")
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    private_permissions(directory)
    with operation_lock(directory):
        secret_path = directory / "secret.key"
        if not os.environ.get("NAVA_SECRET_KEY") and not secret_path.exists():
            with secret_path.open("x", encoding="utf-8") as stream:
                stream.write(secrets.token_urlsafe(64))
            private_permissions(secret_path)
        (directory / "evidence").mkdir(exist_ok=True)
        private_permissions(directory / "evidence")
        if not args.skip_install:
            run([executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", ROOT / "requirements.txt"])
        for command in (["migrate", "--noinput"], ["seed_framework"], ["bootstrap_roles"], ["collectstatic", "--noinput"], ["check"]):
            run([executable, ROOT / "manage.py", *command])
        if not args.no_admin:
            if sys.stdin.isatty():
                response = input("Create an administrator account now? [y/N] ").strip().lower()
                if response == "y":
                    run([executable, ROOT / "manage.py", "createsuperuser"])
            else:
                print("Noninteractive setup: administrator creation skipped.")
    print("Setup completed. Start with: python scripts/start.py")
    print("If no account exists, run the virtual-environment Python with manage.py createsuperuser.")
    print("An administrator must be explicitly assigned a business role before business approvals are available.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        fail(str(exc))
