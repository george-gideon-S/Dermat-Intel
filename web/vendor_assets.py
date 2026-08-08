"""Download ECharts + Geist fonts into web/vendor/ so the app is fully self-contained & offline.

Uses the Windows trusted-cert bundle (node_ca_bundle.pem) so it works behind the AV/proxy TLS
interception that breaks normal HTTPS downloads on this machine.
"""
import os
from pathlib import Path

import requests

CA = os.path.join(os.environ.get("USERPROFILE", ""), "node_ca_bundle.pem")
VERIFY = CA if os.path.exists(CA) else True
VENDOR = Path(__file__).resolve().parent / "vendor"
VENDOR.mkdir(parents=True, exist_ok=True)

ASSETS = {
    "echarts.min.js": "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js",
    # v3 ships weights 300–600 only; 700 is banned by the atlas (§6) and the
    # private dist no longer inlines it. 300 carries the display-light register.
    "geist-300.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist@latest/latin-300-normal.woff2",
    "geist-400.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist@latest/latin-400-normal.woff2",
    "geist-500.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist@latest/latin-500-normal.woff2",
    "geist-600.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist@latest/latin-600-normal.woff2",
    "geist-700.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist@latest/latin-700-normal.woff2",
    "geistmono-400.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist-mono@latest/latin-400-normal.woff2",
    "geistmono-500.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/geist-mono@latest/latin-500-normal.woff2",
}

ok, failed = [], []
for name, url in ASSETS.items():
    dest = VENDOR / name
    if dest.exists() and dest.stat().st_size > 0:
        ok.append(f"{name} (cached {dest.stat().st_size // 1024} KB)")
        continue
    try:
        r = requests.get(url, verify=VERIFY, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        dest.write_bytes(r.content)
        ok.append(f"{name} ({len(r.content) // 1024} KB)")
    except Exception as exc:
        failed.append(f"{name}: {type(exc).__name__} {str(exc)[:80]}")

print("OK:")
for x in ok:
    print("  +", x)
if failed:
    print("FAILED:")
    for x in failed:
        print("  -", x)
print(f"\n{len(ok)}/{len(ASSETS)} assets available in {VENDOR}")
