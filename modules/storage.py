"""Lightweight JSON persistence so the dashboard reloads prior results without re-scraping.

The user-facing exports stay as .xlsx; these JSON files are the app's internal state store.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules import atomicio

def queries_json() -> str:
    """Resolved at call time so config.activate_run() can repoint it at a run snapshot."""
    return str(Path(config.CACHE_DIR) / "query_rows.json")


def results_json() -> str:
    return str(Path(config.CACHE_DIR) / "result_rows.json")


class _LazyPath(str):
    """Back-compat shim: `storage.QUERIES_JSON` still reads as a str, but resolves per access.

    The module-level constants were captured at import time, which silently defeated run
    scoping (a reassigned config.CACHE_DIR would not be seen). Subclassing str keeps every
    existing caller — including open(), Path() and the 133 existing tests — working unchanged.
    """

    def __new__(cls, resolver):
        obj = super().__new__(cls, resolver())
        obj._resolver = resolver
        return obj

    def _current(self) -> str:
        return self._resolver()

    def __str__(self) -> str:
        return self._current()

    def __fspath__(self) -> str:
        return self._current()

    def __eq__(self, other) -> bool:
        return self._current() == other

    def __hash__(self) -> int:
        return hash(self._current())

    def __repr__(self) -> str:
        return repr(self._current())


QUERIES_JSON = _LazyPath(queries_json)
RESULTS_JSON = _LazyPath(results_json)


def save_rows(path: str, rows: list) -> None:
    atomicio.write_json(os.fspath(path), rows)


def load_rows(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_meta(meta: dict) -> None:
    atomicio.write_json(config.METADATA_FILE, meta)


def load_meta() -> dict:
    try:
        with open(config.METADATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
