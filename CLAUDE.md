# Derma Intel — working agreement

Market-intelligence pipeline for medical clinics in Indian cities. It scrapes Google Search and
Google Maps, scores each clinic's online visibility, and writes an immutable dated snapshot per
`(geography, practice, subject_type, run_date)`. The product is sold **to the clinics
themselves**, so language is diagnostic and never accusatory.

Python only today. A premium clinic-facing dashboard and report UI is the next phase.

---

## Environment — this machine bites

- **`python` on PATH is broken.** Use the full path:
  `C:\Users\SALE PITCHAIAH\AppData\Local\Programs\Python\Python310\python.exe`
- **`python -m` does not work.** Invoke scripts by path.
- Embeddable distribution, isolated mode: a script's own directory is **not** on `sys.path`.
  Every entry point needs the 3-line bootstrap that `run_pipeline.py` already carries.
- **TLS interception breaks Python `requests` and npm.** `curl` works (schannel). Shell out to
  curl for outbound HTTP. **Never disable TLS verification.**
- Secrets live in the gitignored `.env`; committed configs reference `${VAR}`. Never inline a
  key on a command line.

## Standing rules

- **Free and keyless.** No paid APIs, no billing, no trial keys. The margin depends on it.
- **Never solve a CAPTCHA programmatically.** A human solves it; the runner may only *notice*
  that one was solved.
- **Blocked is never empty.** Every query ends in exactly one recorded status. A wall recorded
  as "no results" is the defect this whole subsystem exists to prevent.
- **Snapshots are immutable.** A run must never damage an earlier one.
- **Degrade loudly.** Say what failed and what partial data survived. Never let a scraper
  failure read as a market finding.
- Query rules live in [`query writing.md`](query%20writing.md) — read it before touching query
  generation.
- **Never generate imagery of a real clinic.** Clinic names, ratings and reviews here are
  measured data; a generated image beside them would be a fabrication.

---

## MCPs

- **Stitch** — declared in [`.mcp.json`](.mcp.json); it reads `${STITCH_API_KEY}` from the
  gitignored `.env`. Never inline the key.
- **codebase-memory** — indexes this repo into a queryable graph of files, functions,
  calls, routes and complexity. Reach for its graph queries instead of grepping when you
  need to find a definition or trace who calls what. `python tools/graph_viewer.py`
  rebuilds the browsable map and serves it at <http://127.0.0.1:8765>.

Anything else is configured at the account level and is not part of this project.
