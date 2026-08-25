"""Small keyless HTTP GET that survives this machine's TLS interception.

The corporate/AV TLS proxy on this box breaks some Python HTTPS clients while `curl.exe`
works, because curl uses schannel and the Windows certificate store. So: try `requests`
first, fall back to shelling out to curl, and **never** disable certificate verification —
turning verification off would trade a working setup for a silently insecure one.

Used for the free, keyless endpoints only (Google autocomplete, OSM). Browser traffic goes
through nodriver/Playwright, which have their own trust story.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional

DEFAULT_TIMEOUT = 20
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")


class FetchError(Exception):
    """Both transports failed. Callers degrade loudly rather than pretending success."""


def _via_requests(url: str, timeout: int, headers: dict) -> Optional[str]:
    try:
        import requests
    except ImportError:  # pragma: no cover
        return None
    try:
        r = requests.get(url, timeout=timeout, headers=headers)
        if r.status_code == 200:
            return r.text
        return None
    except Exception:
        return None


def _via_curl(url: str, timeout: int, headers: dict) -> Optional[str]:
    exe = shutil.which("curl") or shutil.which("curl.exe")
    if not exe:
        return None
    cmd = [exe, "-s", "--fail", "--max-time", str(timeout)]
    for k, v in headers.items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def get_text(url: str, timeout: int = DEFAULT_TIMEOUT,
             headers: Optional[dict] = None) -> str:
    """GET a URL as text, or raise FetchError. Never silently returns empty on failure."""
    hdrs = {"User-Agent": DEFAULT_UA, "Accept-Language": "en-IN,en;q=0.9"}
    hdrs.update(headers or {})
    for transport in (_via_requests, _via_curl):
        body = transport(url, timeout, hdrs)
        if body is not None:
            return body
    raise FetchError(f"both requests and curl failed for {url}")


def get_json(url: str, timeout: int = DEFAULT_TIMEOUT,
             headers: Optional[dict] = None) -> object:
    body = get_text(url, timeout=timeout, headers=headers)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"non-JSON response from {url}: {exc}") from exc
