"""Build the custom ECharts bundle for the private dist.

The full ECharts UMD build is 1.03 MB and dominates the artifact. v3 only needs
ECharts for the three charts that want real interaction machinery (brush,
dataZoom, hit-testing across 34+ points); every other instrument is hand-authored
SVG. Tree-shaking to just those parts costs ~350 KB instead.

This runs at VENDOR time, not build time — the output is committed to
web/vendor/ and `build_web.py` simply inlines it. The artifact stays offline and
self-contained; Node is a development dependency only.

Why not npm: this machine has TLS interception. npm ignores both NODE_EXTRA_CA_CERTS
and --use-system-ca for its own registry requests, and the exported cert bundle that
works for jsdelivr does not carry the registry's chain. `curl` on Windows uses
schannel and therefore the system cert store, which DOES trust the intercepting root
— the same principle as the `git -c http.sslBackend=schannel` workaround in
CLAUDE.md. So we fetch the registry tarballs with curl and invoke the esbuild binary
out of its package directly. TLS verification is never disabled.

    python web/build_echarts.py
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

WEB = Path(__file__).resolve().parent
VENDOR = WEB / "vendor"
WORK = WEB / ".echarts-build"          # gitignored scratch
OUT = VENDOR / "echarts-custom.min.js"

ECHARTS_VERSION = "5.5.1"
REGISTRY = "https://registry.npmjs.org"

# Exactly what the three ECharts panels need — M3 opportunity map (scatter +
# brush + dataZoom + graphic zone plates), M4 visibility league (bar + markLine +
# markArea), M7 owned-vs-borrowed butterfly (bar + scatter terminals).
ENTRY = """
import * as echarts from "echarts/core";
import { ScatterChart, BarChart } from "echarts/charts";
import {
  GridComponent, TooltipComponent, BrushComponent, DataZoomComponent,
  MarkLineComponent, MarkAreaComponent, GraphicComponent, AxisPointerComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  ScatterChart, BarChart,
  GridComponent, TooltipComponent, BrushComponent, DataZoomComponent,
  MarkLineComponent, MarkAreaComponent, GraphicComponent, AxisPointerComponent,
  CanvasRenderer,
]);

// The app calls echarts.init(...) off the global, exactly as the UMD build allows.
window.echarts = echarts;
"""


def _get(url: str) -> bytes:
    """GET with TLS verification, via curl's schannel backend (system cert store)."""
    proc = subprocess.run(["curl", "-sSL", "--fail", "--max-time", "300", url],
                          capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"download failed: {url}\n{proc.stderr.decode(errors='replace')}")
    return proc.stdout


def fetch_tarball(name: str, version: str, dest: Path) -> Path:
    """Download and extract an npm tarball without going through npm."""
    short = name.split("/")[-1]
    url = f"{REGISTRY}/{name}/-/{short}-{version}.tgz"
    print(f"  fetching {name}@{version}")
    with tarfile.open(fileobj=io.BytesIO(_get(url)), mode="r:gz") as tf:
        tf.extractall(dest)          # npm tarballs always root at "package/"
    out = dest / "package"
    final = dest / short
    if final.exists():
        shutil.rmtree(final)
    out.rename(final)
    return final


def latest_version(name: str) -> str:
    return json.loads(_get(f"{REGISTRY}/{name}/latest"))["version"]


def esbuild_binary(work: Path) -> Path:
    """Fetch the platform esbuild package and return the executable inside it.

    The `esbuild` wrapper package downloads its binary in a postinstall script;
    the platform package (@esbuild/win32-x64 and friends) ships the binary
    directly, so we take that and skip the script entirely.
    """
    plat = {
        ("win32", "x86_64"): ("@esbuild/win32-x64", "esbuild.exe"),
        ("win32", "AMD64"): ("@esbuild/win32-x64", "esbuild.exe"),
        ("darwin", "arm64"): ("@esbuild/darwin-arm64", "bin/esbuild"),
        ("darwin", "x86_64"): ("@esbuild/darwin-x64", "bin/esbuild"),
        ("linux", "x86_64"): ("@esbuild/linux-x64", "bin/esbuild"),
    }
    import platform
    key = (sys.platform, platform.machine())
    if key not in plat:
        raise SystemExit(f"no esbuild mapping for {key}; add one to build_echarts.py")
    pkg, rel = plat[key]
    version = latest_version(pkg)
    root = fetch_tarball(pkg, version, work)
    exe = root / rel
    if not exe.exists():
        raise SystemExit(f"esbuild binary not found at {exe}")
    exe.chmod(0o755)
    return exe


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    echarts_root = fetch_tarball("echarts", ECHARTS_VERSION, WORK)

    # esbuild resolves bare "echarts/core" specifiers through node_modules.
    node_modules = WORK / "node_modules"
    node_modules.mkdir(exist_ok=True)
    link = node_modules / "echarts"
    if link.exists():
        shutil.rmtree(link, ignore_errors=True)
    shutil.copytree(echarts_root, link)

    # ECharts' own deps (zrender, tslib) must resolve too.
    pkg = json.loads((echarts_root / "package.json").read_text(encoding="utf-8"))
    for dep, spec in (pkg.get("dependencies") or {}).items():
        version = spec.lstrip("^~>=< ").split(" ")[0]
        dep_root = fetch_tarball(dep, version, WORK)
        target = node_modules / dep
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(dep_root, target)

    entry = WORK / "entry.js"
    entry.write_text(ENTRY, encoding="utf-8")

    exe = esbuild_binary(WORK)
    print("  bundling…")
    subprocess.run(
        [str(exe), str(entry), "--bundle", "--minify", "--format=iife",
         "--legal-comments=none", f"--outfile={OUT}"],
        cwd=str(WORK), check=True,
    )

    full = VENDOR / "echarts.min.js"
    saved = (full.stat().st_size - OUT.stat().st_size) // 1024 if full.exists() else 0
    print(f"\nwrote {OUT.relative_to(WEB.parent)}  ({OUT.stat().st_size // 1024} KB)")
    if saved:
        print(f"  {saved} KB smaller than the full UMD build")


if __name__ == "__main__":
    main()
