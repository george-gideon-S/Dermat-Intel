/* ── Utilities. No dependencies; first real module in the bundle. ───────────── */
window.DI = window.DI || {};

(function (DI) {
  "use strict";

  /** Build an element. h("div.panel", {span: 7}, child, child) */
  function h(spec, attrs, ...kids) {
    const [tagPart, ...classes] = String(spec).split(".");
    const el = document.createElement(tagPart || "div");
    if (classes.length) el.className = classes.join(" ");
    if (attrs && attrs.constructor === Object) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === null || v === undefined || v === false) continue;
        // Deliberately NO innerHTML escape hatch. Clinic names come from scraped
        // Google Maps listings and are untrusted; every text path below goes
        // through textContent / createTextNode so markup can never execute.
        // Custom properties MUST go through setProperty — Object.assign(style, …)
        // silently drops anything starting with "--", which is how every panel
        // ended up full-width the first time.
        if (k === "style" && typeof v === "object") {
          for (const [pk, pv] of Object.entries(v)) {
            if (pk.startsWith("--")) el.style.setProperty(pk, pv);
            else el.style[pk] = pv;
          }
        }
        else if (k === "text") el.textContent = v;
        else if (k.startsWith("on") && typeof v === "function") {
          el.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (k === "data" && typeof v === "object") {
          for (const [dk, dv] of Object.entries(v)) {
            if (dv !== null && dv !== undefined) el.dataset[dk] = dv;
          }
        } else el.setAttribute(k, v === true ? "" : v);
      }
    } else if (attrs !== undefined && attrs !== null) {
      kids.unshift(attrs);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  /** SVG element builder — same shape as h(), different namespace. */
  const NS = "http://www.w3.org/2000/svg";
  function s(tag, attrs, ...kids) {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "data" && typeof v === "object") {
        for (const [dk, dv] of Object.entries(v)) {
          if (dv !== null && dv !== undefined) el.dataset[dk] = dv;
        }
      } else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  /** ECharts tooltip formatters must return an HTML string, so that one path
   *  cannot use textContent. Everything interpolated into a formatter goes
   *  through here. */
  const esc = (v) => String(v === null || v === undefined ? "" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  /** Integers with thin separators; nulls become an em dash, never "0" or "null". */
  const num = (v, dp) => (v === null || v === undefined || Number.isNaN(v))
    ? "—"
    : (dp === undefined ? Math.round(v).toLocaleString("en-IN")
                        : Number(v).toFixed(dp));

  const pct = (v, dp = 0) => (v === null || v === undefined) ? "—"
    : `${(v * 100).toFixed(dp)}%`;

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  /** FNV-1a. Deterministic jitter everywhere — Math.random() is banned by the
   *  design laws because it makes verifier screenshots irreproducible. */
  function hash32(str) {
    let hsh = 2166136261;
    for (let i = 0; i < str.length; i++) {
      hsh ^= str.charCodeAt(i);
      hsh = Math.imul(hsh, 16777619);
    }
    return hsh >>> 0;
  }
  /** Stable pseudo-random in [0,1) from any seed string. */
  const rand = (seed) => (hash32(String(seed)) % 100000) / 100000;

  /** Collapse repeated calls into one per animation frame. Hover fires on every
   *  pointermove; without this the bus would thrash the whole canvas. */
  function coalesce(fn) {
    let queued = false, lastArgs = null;
    return function (...args) {
      lastArgs = args;
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; fn.apply(null, lastArgs); });
    };
  }

  const median = (arr) => {
    const a = arr.filter((v) => v !== null && v !== undefined).slice().sort((x, y) => x - y);
    if (!a.length) return 0;
    const m = a.length >> 1;
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  };

  /** Truncate on a word boundary where possible — clinic names are long. */
  const short = (str, n) => {
    const t = String(str || "");
    if (t.length <= n) return t;
    const cut = t.slice(0, n);
    const sp = cut.lastIndexOf(" ");
    return (sp > n * 0.6 ? cut.slice(0, sp) : cut).trimEnd() + "…";
  };

  const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  Object.assign(DI, { h, s, esc, num, pct, clamp, hash32, rand, coalesce, median, short, reduced });
})(window.DI);
