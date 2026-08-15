# Session handoff — v3 shipped, v4 approved and ready to start

**Read this, then `C:\Users\SALE PITCHAIAH\.claude\plans\the-current-website-feels-bubbly-gosling.md`
(the approved v4 brief). Start at V0.**

---

## Where things stand

**v3 is complete and committed** (`e1ffb85`). Seven gates cleared: identity re-derived by
measuring the reference images, payload widened, shell + cross-filter runtime, 8 clinic
panels, 11 market panels, verification.

| Check | Command | Expected |
|---|---|---|
| Tests | `python -m pytest -q` | **384 passed** |
| Verifier | `python docs/redesign/v3/tools/verify_dashboard.py` | **33/33** |
| Build | `python web/build_web.py` | ~1036 KB, 34 clinics |
| Public dist | `python web/build_web.py --public` | sha256 must match `verification/BASELINE.json` |

Private dist went 1322 KB → 1036 KB. Payload 215 KB → 193 KB.

---

## What v4 is, in one line

**v3 fixed the styling; it did not fix the layout.** The pages are still one column of
tall sections full of prose. v4 rebuilds them as **cards** — small, one-idea-each, in a
varied bento — with top-pill navigation, a dedicated clinic-picker screen, no sidebar
filters, and a real map surface. The brand system carries forward unchanged.

Three background variants get built and compared: **map · dot-matrix map · generated
gradient**. Expect the dot map to win (it makes our dot motif land at a fourth scale),
but build all three.

---

## Things that will bite a fresh session

**1 · The new inspiration images are in the OTHER project.**
`E:\TRINADE\LOG APP V2\Design\Design Inspiration\Added Inspiration\`
— `Glucose Monitoring Dashboard 1/2/3.png` (shell + card grammar)
— `Dashboard for Market section.png` (map treatment)
— `Warm Translucent background dashboard.jpeg` (glass-over-subject + **the dotted map**)

**2 · Python is running on a patched-together runtime.**
It was removed from this machine on 2026-08-10 (binaries and stdlib gone, `site-packages`
left intact). Restored using the official **embeddable** distribution copied into
`%LOCALAPPDATA%\Programs\Python\Python310`, with a hand-written `python310._pth`:

```
python310.zip
.
Lib\site-packages
Scripts
import site
```

If Python breaks again, that file is the first thing to check. Do **not** write it with
PowerShell `-Encoding utf8` — the BOM corrupts the first `sys.path` entry. Use ASCII.
`Python310` + `Python310\Scripts` were also prepended to the **user** PATH.

**3 · There is an unresolved security finding on this machine.**
Windows Security Center has an "antivirus" registered as **`dnot.sh`** with
`pathToSignedReportingExe` pointing at `Taskmgr.exe`, and **Defender is disabled as a
result** (`AMRunningMode: Not running`). It registered 2026-08-10 02:10; the Python folder
was stripped the same day at 07:14 and `miniconda3` was deleted entirely. Not fixed —
flagged to George, his call. Does not block the work.

**4 · npm cannot reach the registry** through the TLS interception (it ignores both
`NODE_EXTRA_CA_CERTS` and `--use-system-ca`). **`curl` works** — it uses schannel and the
Windows cert store. That is how `web/build_echarts.py` fetches tarballs. Never disable
TLS verification.

**5 · `design/` (13 MB) is still untracked.** The probe map reads from it, so verification
cannot be reproduced from a fresh clone. George's call whether to commit it.

---

## Hard-won gotchas — do not relearn these

- `Object.assign(el.style, …)` **silently drops custom properties**. Use `setProperty`, or
  every panel renders full-width.
- `[hidden]` is only `display:none` at UA level; any `display` rule defeats it. There is a
  global `[hidden]{display:none!important}` in `00-reset.css` — keep it.
- **The numeric prefix in `web/js/` IS the load order.** Panels call `DI.app.register()` at
  parse time, so `70-app` must precede `80-`/`85-`. A test asserts it. Getting this wrong
  gives a blank page with a useless error.
- **ECharts ignores `itemStyle` callbacks** for `opacity`/`borderWidth` (only `color`
  works). Use per-datum `itemStyle` or the series renders invisible.
- A **`markArea` on the same series** as its marks paints over them. Give plates their own
  silent `z:0` series.
- **ECharts brush needs `takeGlobalCursor`** — declaring `brush: {}` is not enough, and
  `setOption` resets it, so re-arm after every update.
- **Chromium `full_page` screenshots do not repaint `<canvas>`** on long pages. Size the
  viewport to the document (`shoot_tall` in the verifier).
- `.panel__body` must be a flex column or charts sit at min-height inside tall panels —
  that was the "dead card space" complaint.

---

## Known-open items (not blocking v4)

1. **`web/public_data.py:146` reads a key that has never existed.** It checks a top-level
   `clinic["has_own_site"]`; the payload only nests it under `clinic["web"]`. The live
   public page therefore claims **0 of 34** clinics rank on their own site, contradicting
   the paid report (12 do). Predates this rebuild. Fixing it changes public dist bytes, so
   it needs a deliberate re-baseline of `BASELINE.json` plus a fixture fix in
   `tests/test_public_data.py:20`.
2. ~40 KB of the private payload has no consumer.
3. `config.WHATSAPP_NUMBER` and the Razorpay links are still `""`.

---

## Start here

**V0 · Card inventory.** Enumerate every card the data supports (target 25–35) with size,
content and viz type; define the bento at 1440 and its reflow. George approves the
inventory before any pixels get drawn.

The data inventory to draw from is in the plan file under *"The data available"* — plus
the traps list, which matters as much: `rating` is useless (28 of 34 sit 4.8–5.0),
`ai_overview` is 0 everywhere, review NLP is ~10 reviews/clinic with no dates, and the
three denominators are **50 Maps queries · 78 SERPs · 80 total**.
