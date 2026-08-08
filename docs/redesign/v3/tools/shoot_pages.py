"""Screenshot the built private report (Your Clinic + The Market) at desktop and phone widths.

Used for the v3 before/after contact sheet. Reads the dist over file:// so it also
proves the artifact renders standalone.

    python docs/redesign/v3/tools/shoot_pages.py before
    python docs/redesign/v3/tools/shoot_pages.py after
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]  # tools -> v3 -> redesign -> docs -> repo
DIST = ROOT / "web" / "dist" / "index.html"
VIEWPORTS = {"1440": (1440, 900), "390": (390, 844)}


def shoot(label: str) -> None:
    out = ROOT / "docs" / "redesign" / "v3" / "verification" / label
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, (w, h) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            page.goto(DIST.as_uri())
            page.wait_for_timeout(2500)  # fonts + ECharts first paint

            for view in ("clinic", "market"):
                page.click(f'.topbar [data-nav="{view}"]')
                page.wait_for_timeout(1600)
                path = out / f"{view}-{vp_name}.png"
                page.screenshot(path=str(path), full_page=True)
                print(f"  {path.relative_to(ROOT)}")
            page.close()
        browser.close()


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "before"
    print(f"Shooting '{label}' from {DIST.relative_to(ROOT)}")
    shoot(label)
