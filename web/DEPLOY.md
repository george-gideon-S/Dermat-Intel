# Deploying Derma Intel (Vercel + Bitly)

The build emits a **fully static, self-contained** folder at `web/dist/` — `index.html` (CSS/JS/fonts/
ECharts/GSAP all inlined), the bundled `proof/` screenshots, and a `vercel.json`. The same folder works
on `file://` and on any static host. No server, no env vars, no API keys.

## 1 · Build
```
python web/build_web.py
```
→ `web/dist/index.html` + `web/dist/proof/` + `web/dist/vercel.json`.

> Vercel **cannot** build this itself — the build needs Python and the gitignored `.cache/` (clinic data)
> + `data/Full Page Screenshots/` (proof images). **Always build locally, then deploy the `dist/` folder.**

## 2 · Deploy to Vercel (static, free)
Pick one:
- **Drag-and-drop:** drag `web/dist/` onto https://vercel.com (New Project → deploy the folder).
- **CLI:** `cd web/dist && npx vercel deploy --prod` (first run links/creates the project).

Vercel serves `index.html` at the root; `cleanUrls` is on. You get a `https://<name>.vercel.app` URL.

## 3 · Shorten with Bitly
Paste the `*.vercel.app` URL into https://bitly.com to get a clean short link to share with clinics.

## Notes
- Re-deploy after any rebuild (the dist is regenerated each build).
- Everything is offline-capable; opening `web/dist/index.html` directly also works.
- Reduced-motion and no-JS both degrade to a readable, static narrative.
