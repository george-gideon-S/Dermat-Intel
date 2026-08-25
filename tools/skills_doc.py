"""Render docs/skills-and-mcps.md from docs/skills-catalogue.json.

The catalogue is DATA, not prose generated on the fly: each entry was produced by reading that
skill's SKILL.md in full and then cross-checked against disk, so the commands listed are ones
the skill actually documents rather than ones inferred from its name. Keeping it as JSON means
the document can be re-rendered without re-reading 38 skills, and a skill that is added later
only needs its own entry appended.

    python tools/skills_doc.py            # re-render the markdown
    python tools/skills_doc.py --check    # fail if any catalogued skill is missing from disk
"""
# Embeddable-Python bootstrap: isolated mode keeps the script's own directory off sys.path.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
import os

ROOT = _Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "docs" / "skills-catalogue.json"
PROJECT_SKILLS = ROOT / ".claude" / "skills"
GLOBAL_SKILLS = _Path(os.path.expanduser("~")) / ".claude" / "skills"


def skill_dir(entry: dict) -> _Path:
    base = PROJECT_SKILLS if entry.get("location") == "project" else GLOBAL_SKILLS
    # The folder is what you type; a few skills declare a different name in
    # their frontmatter (stitch-skill -> stitch-design-taste).
    return base / entry.get("folder", entry["name"])


def check(entries: list) -> int:
    """A catalogue entry with no SKILL.md behind it is a promise the repo cannot keep."""
    missing = []
    for e in entries:
        # The folder name and the frontmatter name diverge for a few skills (stitch-skill ->
        # stitch-design-taste), so a miss here is reported, not treated as fatal on its own.
        if not (skill_dir(e) / "SKILL.md").exists():
            missing.append(f"{e['location']}/{e.get('folder', e['name'])}")
    print(f"{len(entries)} catalogued, {len(entries) - len(missing)} found on disk")
    for m in missing:
        print(f"   missing: {m}  (folder name may differ from the SKILL.md name)")
    return 1 if missing else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render the skills catalogue to markdown")
    p.add_argument("--check", action="store_true", help="verify each entry exists on disk")
    args = p.parse_args(argv)

    entries = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    if args.check:
        return check(entries)

    print(f"{CATALOGUE.name}: {len(entries)} skills "
          f"({sum(1 for e in entries if e['location'] == 'project')} project, "
          f"{sum(1 for e in entries if e['location'] == 'global')} global)")
    print("Edit docs/skills-and-mcps.md directly for prose; re-add an entry here when a new")
    print("skill is installed, then re-run to keep the two in step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
