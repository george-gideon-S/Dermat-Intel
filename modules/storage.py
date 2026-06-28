"""Lightweight JSON persistence so the dashboard reloads prior results without re-scraping.

The user-facing exports stay as .xlsx; these JSON files are the app's internal state store.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

QUERIES_JSON = str(Path(config.CACHE_DIR) / "query_rows.json")
RESULTS_JSON = str(Path(config.CACHE_DIR) / "result_rows.json")


def save_rows(path: str, rows: list) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)


def load_rows(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_meta(meta: dict) -> None:
    Path(config.METADATA_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(config.METADATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)


def load_meta() -> dict:
    try:
        with open(config.METADATA_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
