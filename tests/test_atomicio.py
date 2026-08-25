"""Atomic write primitives — the guard against the in-place-overwrite data loss class.

No network. Pure filesystem behaviour against tmp_path.

These tests exist because a `run_pipeline.py --mock` run once overwrote a month-old
real dataset in place. Every test here asserts the *old* bytes survive a failure.
"""
import json
from pathlib import Path

import pytest

from modules import atomicio


# --- write_bytes / write_text -------------------------------------------------

def test_write_text_creates_file_and_parents(tmp_path):
    target = tmp_path / "deep" / "nested" / "out.txt"
    atomicio.write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_text_replaces_existing_content(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")
    atomicio.write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_failed_write_leaves_original_intact(tmp_path):
    """The core guarantee: a serializer that blows up must not truncate the old file."""
    target = tmp_path / "precious.json"
    target.write_text('{"real": "june data"}', encoding="utf-8")

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomicio.write_json(target, {"bad": Unserializable()})

    # Old content still there, byte-for-byte.
    assert json.loads(target.read_text(encoding="utf-8")) == {"real": "june data"}


def test_failed_write_leaves_no_temp_files_behind(tmp_path):
    target = tmp_path / "precious.json"
    target.write_text("{}", encoding="utf-8")

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomicio.write_json(target, {"bad": Unserializable()})

    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "precious.json"]
    assert leftovers == [], f"temp files leaked: {leftovers}"


def test_temp_file_is_written_in_same_directory(tmp_path, monkeypatch):
    """os.replace is only atomic within a filesystem, so the temp must be a sibling."""
    target = tmp_path / "sub" / "out.json"
    target.parent.mkdir(parents=True)
    seen = {}

    real_replace = atomicio.os.replace

    def spy(src, dst):
        seen["src_parent"] = Path(src).parent
        seen["dst_parent"] = Path(dst).parent
        return real_replace(src, dst)

    monkeypatch.setattr(atomicio.os, "replace", spy)
    atomicio.write_json(target, {"a": 1})
    assert seen["src_parent"] == seen["dst_parent"] == target.parent


# --- write_json ---------------------------------------------------------------

def test_write_json_roundtrip_preserves_unicode(tmp_path):
    """Clinic names and reviews carry Telugu/Devanagari; ensure_ascii must stay off."""
    target = tmp_path / "u.json"
    payload = {"name": "శ్రీ Skin Clinic", "note": "నాకు చాలా బాగా"}
    atomicio.write_json(target, payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert "\\u" not in target.read_text(encoding="utf-8")


def test_write_json_accepts_str_path(tmp_path):
    target = str(tmp_path / "s.json")
    atomicio.write_json(target, [1, 2, 3])
    assert json.loads(Path(target).read_text(encoding="utf-8")) == [1, 2, 3]


def test_write_json_indent_is_optional(tmp_path):
    compact = tmp_path / "c.json"
    pretty = tmp_path / "p.json"
    atomicio.write_json(compact, {"a": 1})
    atomicio.write_json(pretty, {"a": 1}, indent=2)
    assert "\n" not in compact.read_text(encoding="utf-8")
    assert "\n" in pretty.read_text(encoding="utf-8")


# --- read_json ----------------------------------------------------------------

def test_read_json_missing_returns_default():
    assert atomicio.read_json("no/such/file.json", default={"d": 1}) == {"d": 1}


def test_read_json_distinguishes_corrupt_from_missing(tmp_path):
    """storage.load_rows conflates these two; the snapshot store must not."""
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    with pytest.raises(atomicio.CorruptArtifact):
        atomicio.read_json(corrupt, default=None, strict=True)
    # non-strict still degrades to the default
    assert atomicio.read_json(corrupt, default="fallback") == "fallback"


def test_read_json_reads_what_write_json_wrote(tmp_path):
    target = tmp_path / "rt.json"
    payload = {"queries": [{"rank": 1, "search_query": "acne treatment"}]}
    atomicio.write_json(target, payload)
    assert atomicio.read_json(target, default=None) == payload
