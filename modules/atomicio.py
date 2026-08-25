"""Atomic file writes: write to a sibling temp file, then os.replace.

Every artifact in a run snapshot goes through here. The rule this enforces is that a
half-finished or failed write can never damage the file it was replacing — os.replace is
atomic within a filesystem, so a reader either sees the whole old file or the whole new one.

The temp file is always created in the *destination directory* (not the system temp dir),
because os.replace is only atomic within a single filesystem.

`read_json` deliberately separates "missing" from "corrupt": modules/storage.py returns None
for both, which makes a truncated file look identical to a fresh start. Snapshot artifacts
must be able to tell those apart.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Union

StrPath = Union[str, "os.PathLike[str]"]


class CorruptArtifact(Exception):
    """A file exists but could not be parsed — distinct from the file being absent."""


def _atomic_write(path: StrPath, data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(target))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_bytes(path: StrPath, data: bytes) -> None:
    _atomic_write(path, data)


def write_text(path: StrPath, text: str, encoding: str = "utf-8") -> None:
    _atomic_write(path, text.encode(encoding))


def write_json(path: StrPath, payload: Any, indent: int | None = None) -> None:
    """Serialize first, write second — a serialization error must not touch the target."""
    blob = json.dumps(payload, ensure_ascii=False, indent=indent)
    _atomic_write(path, blob.encode("utf-8"))


def read_json(path: StrPath, default: Any = None, strict: bool = False) -> Any:
    """Read JSON. Missing -> default. Corrupt -> default, or CorruptArtifact if strict."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        if strict:
            raise CorruptArtifact(f"{path}: {exc}") from exc
        return default
