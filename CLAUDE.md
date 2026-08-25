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

## Skills — recommend one before you start

**38 skills and 2 MCPs are installed.** The full catalogue, with every documented command, is
[`docs/skills-and-mcps.md`](docs/skills-and-mcps.md).

**The rule: at the start of any design, frontend, animation or UI task — and at each new step
within one — name the skill that would improve the work and say why, before writing code.**
One line is enough: *"`/hallmark` would fix the structural sameness here — want me to load
it?"* If nothing genuinely fits, say so instead of forcing one. A skill that does not apply
costs more than it gives.

### Routing table

| The task | Reach for |
|---|---|
| New page or screen, nothing designed yet | `/hallmark` (structure + anti-slop gates), `/taste-skill` |
| Existing UI feels generic or templated | `/redesign-skill`, `/hallmark audit` |
| Polish, spacing, hierarchy, a11y, states | `/impeccable` (26 commands — `/impeccable audit` first) |
| Extract or lock a design language | `/design-dna`, `/stitch-skill` (writes DESIGN.md) |
| Build one animation | `/animate` — CSS/WAAPI first, no framework needed |
| Judge or fix existing motion | `/review-animations`, `/improve-animations` |
| Find where motion is missing | `/find-animation-opportunities` |
| Gesture, spring, momentum, depth | `/apple-design` |
| Timing, easing, stagger values | `/motion-design` |
| GSAP specifically | `/gsap-core`, `/gsap-scrolltrigger`, `/gsap-timeline`, … |
| Naming an effect you can only describe | `/animation-vocabulary` |
| About to add a frontend dependency | `/pick-ui-library` — do not hand-roll |
| Several takes on one component | `/prototype` |
| Screen comps from a brief | Stitch MCP + `/stitch-skill` |
| Reference imagery you do not have | Higgsfield MCP, `/imagegen-frontend-web` |
| Code feels over-engineered | `/ponytail-review` (diff), `/ponytail-audit` (repo) |
| Output too verbose | `/caveman` |
