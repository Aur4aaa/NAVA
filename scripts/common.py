"""Small, standard-library-only helpers shared by operational commands."""
from __future__ import annotations

import contextlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def data_directory() -> Path:
    value = os.environ.get("NAVA_DATA_DIR")
    return Path(value).expanduser().resolve() if value else ROOT / ".runtime"


def python_executable() -> Path:
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command: list[str | Path], *, env: dict | None = None) -> None:
    subprocess.run([str(part) for part in command], cwd=ROOT, env=env, check=True)


def private_permissions(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o700 if path.is_dir() else 0o600)


@contextlib.contextmanager
def operation_lock(directory: Path):
    """Coordinate managed server and maintenance operations; never use stale PID locks."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "operation.lock"
    stream = None
    try:
        try:
            # Windows byte-range locks also prevent reads of the locked byte.
            # Inspect file metadata rather than reading it before acquisition.
            # An unbuffered handle prevents a deferred flush after a failed lock.
            stream = path.open("a+b", buffering=0)
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("NAVA is running or another maintenance operation holds the lock. Stop it before continuing.") from exc
        yield
    finally:
        # Closing the acquired handle releases its OS lock, including when the
        # protected operation raises. A failed contender closes only its handle.
        if stream is not None:
            stream.close()


def fail(message: str) -> None:
    print(f"NAVA: {message}", file=sys.stderr)
    raise SystemExit(1)
