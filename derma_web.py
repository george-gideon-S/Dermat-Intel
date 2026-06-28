"""Build the premium Derma Intel web interface from the latest data and open it in your browser.

Usage:
    python derma_web.py

This rebuilds web/dist/derma_intel.html (a single self-contained, offline file) from the current
pipeline results and opens it. No server is started — there is nothing to keep running.
Refresh the data first with `python run_pipeline.py` (or the Streamlit "Run Pipeline" button).
"""
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "web"))

import build_web  # noqa: E402  (path set above)


def main():
    out = build_web.build()
    uri = Path(out).resolve().as_uri()
    print("Opening", uri)
    try:
        webbrowser.open(uri)
    except Exception:
        print("Could not auto-open a browser. Open this file manually:\n ", out)


if __name__ == "__main__":
    main()
