/* ── Instruments ──────────────────────────────────────────────────────────────
   Hand-authored SVG and DOM. These are the components that make the dashboard
   read as an instrument rather than a chart library: rulers with one glowing
   point, dot columns that shimmer, filaments that show emptiness, censuses that
   count, and the mesh jewels.

   Three rules from the atlas are enforced here rather than left to callers:
     * rulers are QUOTA-FREE — there is no target line, ever;
     * every marker is a glowing POINT, never a full-height bar (v4 law);
     * jitter is SEEDED — Math.random() is banned so verifier shots reproduce.

   Everything below is additive to what v3 shipped. `tickRuler`, `dotColumn`,
   `jewel`, `metric`, `hilite` and `applyFilterClass` keep their exact v3
   signatures because 85-panels-market.js still calls them. */
(function (DI) {
  "use strict";

  const { s, h, clamp, rand, short } = DI;

  /**
   * Tick ruler (SVG only, stretched with preserveAspectRatio="none").
   * Ticks at 45% alpha, major every 6th, and exactly one full-alpha marker.
   * The marker is a BAR here because the SVG is non-uniformly scaled — a circle
   * would render as an ellipse. Callers that want the v4 point marker use
   * pointRuler() below, which puts the dot in the DOM where it stays round.
   * @param {number} n     tick count
   * @param {number} pos   marker position, 0..1 (null = no marker)
   */
  function tickRuler(n, pos, opts = {}) {
    const pitch = 8, height = opts.height || 22, width = n * pitch;
    const ticks = [];
    for (let i = 0; i < n; i++) {
      const major = i % 6 === 0;
      const hh = major ? height * 0.68 : height * 0.41;
      ticks.push(s("rect", { x: (i * pitch + pitch / 2).toFixed(1), y: height - hh,
                             width: 1.5, height: hh, rx: 0.7 }));
    }
    const kids = [s("g", { class: "tick-group", fill: "currentColor",
                           opacity: opts.tickAlpha || null }, ticks)];
    if (pos !== null && pos !== undefined) {
      const mx = clamp(pos, 0, 1) * (width - 3);
      kids.push(s("rect", {
        class: "ruler-mark", x: mx.toFixed(1), y: 0, width: 3, height,
        rx: 1.5, fill: "currentColor",
      }));
    }
    return s("svg", {
      class: "viz ruler-viz", viewBox: `0 0 ${width} ${height}`,
      height, preserveAspectRatio: "none", "aria-hidden": "true",
    }, kids);
  }

  /**
   * The v4 ruler: the same tick field, but the marker is a glowing POINT in the
   * DOM rather than a bar in the (non-uniformly scaled) SVG. This is the law
   * "no target lines — every marker is a glowing point" made structural: there
   * is no way to ask this instrument for a line.
   * @param {number} n    tick count
   * @param {number} pos  marker position 0..1, or null for a bare scale
   */
  function pointRuler(n, pos, opts = {}) {
    const height = opts.height || 22;
    const el = h("div.ruler", { style: { height: `${height}px` }, "aria-hidden": "true" },
      tickRuler(n, null, { height, tickAlpha: opts.tickAlpha }));
    if (pos !== null && pos !== undefined) {
      el.append(h("i.ruler__dot", { style: { left: `${clamp(pos, 0, 1) * 100}%` } }));
    }
    return el;
  }

  /**
   * A tick field with a filled SPAN from zero, terminated by a glowing point.
   * A span answers "how much of the whole", where a marker answers "where".
   */
  function spanRuler(frac, opts = {}) {
    const height = opts.height || 18;
    const f = clamp(frac, 0, 1);
    return h("div.ruler.ruler--span", { style: { height: `${height}px` }, "aria-hidden": "true" },
      tickRuler(opts.ticks || 28, null, { height }),
      h("i.ruler__fill", { style: { width: `${f * 100}%` } }),
      h("i.ruler__dot", { style: { left: `${f * 100}%` } }));
  }

  /**
   * Dot-column histogram. Alpha is modulated PER COLUMN by its value with a sine
   * on the index, so the field shimmers instead of reading as a flat bar chart.
   * Modulating per dot-row instead fades every column's base into nothing.
   */
  function dotColumn(values, opts = {}) {
    const cell = opts.cell || 5;
    const rows = opts.rows || 9;
    const max = Math.max(...values, 1);
    const width = values.length * cell * 2;
    const height = rows * cell + 4;
    const dots = [];
    values.forEach((v, i) => {
      const n = Math.max(1, Math.round((v / max) * rows));
      let a = 0.42 + 0.5 * (v / max) * (0.6 + 0.4 * Math.sin(i * 1.7 + 1));
      a = clamp(a, 0.3, 0.95);
      const hot = opts.highlight !== undefined && i === opts.highlight;
      for (let r = 0; r < n; r++) {
        dots.push(s("circle", {
          cx: i * cell * 2 + cell, cy: height - 3 - r * cell,
          r: (cell * 0.34).toFixed(2), opacity: hot ? 1 : a.toFixed(2),
          data: opts.keys ? { clinic: opts.keys[i] } : null,
        }));
      }
    });
    return s("svg", {
      class: "viz dot-col", viewBox: `0 0 ${width} ${height}`,
      height: opts.height || height, preserveAspectRatio: "none", "aria-hidden": "true",
    }, s("g", { fill: "currentColor" }, dots));
  }

  /**
   * Dot census — one cell per thing counted, lit where it happened. Three
   * states, because the web corpus has three: lit (owned), half (borrowed),
   * dead (absent). Pass only `lit` for the two-state form.
   *
   * The denominator is the honesty contract, so the census always draws ALL of
   * it — a 50-cell grid with 9 lit says something a "9" alone cannot.
   */
  function dotCensus(total, opts = {}) {
    const lit = opts.lit || 0, half = opts.half || 0;
    const per = opts.per || Math.min(total, 26);
    const cell = opts.cell || 7, r = opts.r || cell * 0.3;
    const rows = Math.ceil(total / per);
    const width = per * cell, height = rows * cell + 2;
    const dots = [];
    for (let i = 0; i < total; i++) {
      const state = i < lit ? "own" : (i < lit + half ? "borrowed" : "none");
      dots.push(s("circle", {
        cx: ((i % per) * cell + cell / 2).toFixed(1),
        cy: (Math.floor(i / per) * cell + cell / 2 + 1).toFixed(1),
        r: r.toFixed(2), class: `census census--${state}`,
      }));
    }
    return s("svg", {
      class: "viz census-viz", viewBox: `0 0 ${width} ${height}`,
      height: height * (opts.scale || 1.6), preserveAspectRatio: "xMinYMid meet",
      "aria-hidden": "true",
    }, dots);
  }

  /** A row of n dots, `lit` of them alight. A meter, not a bar: the eye counts. */
  function dotMeter(n, lit, opts = {}) {
    const cell = opts.cell || 15, r = opts.r || 4.6;
    const dots = [];
    for (let i = 0; i < n; i++) {
      dots.push(s("circle", {
        cx: (i * cell + cell / 2).toFixed(1), cy: (cell / 2).toFixed(1), r,
        class: i < lit ? "meterdot meterdot--lit" : "meterdot",
      }));
    }
    return s("svg", {
      class: "viz meter-viz", viewBox: `0 0 ${n * cell} ${cell}`,
      height: cell * (opts.scale || 1.3), preserveAspectRatio: "xMinYMid meet",
      "aria-hidden": "true",
    }, dots);
  }

  /**
   * Jittered dot grid — one dot per thing actually read. Jitter is seeded off
   * the caller's key so a verifier screenshot reproduces byte for byte.
   */
  function jitterGrid(total, lit, seed, opts = {}) {
    const per = opts.per || 10, cell = opts.cell || 14, r = opts.r || 4.6;
    const spread = opts.spread || 4;
    const dots = [];
    for (let i = 0; i < total; i++) {
      const jx = (rand(`${seed}vx${i}`) - 0.5) * spread;
      const jy = (rand(`${seed}vy${i}`) - 0.5) * spread;
      dots.push(s("circle", {
        cx: ((i % per) * cell + cell / 2 + jx).toFixed(1),
        cy: (Math.floor(i / per) * cell + cell / 2 + jy).toFixed(1),
        r, class: i < lit ? "vdot vdot--pos" : "vdot vdot--neg",
      }));
    }
    const rows = Math.ceil(total / per) || 1;
    return s("svg", {
      class: "viz voice", viewBox: `0 0 ${per * cell} ${rows * cell}`,
      height: rows * cell * (opts.scale || 1.4), preserveAspectRatio: "xMinYMid meet",
      "aria-hidden": "true",
    }, dots);
  }

  /**
   * Dumbbell — you against one market comparator on a hairline track, with an
   * optional ghost tick for a second (skewed) comparator.
   * `sqrt` scaling survives the 22 ↔ 2,085 review spread that flattens a linear
   * track into two dots at the same end.
   */
  function dumbbell(you, market, opts = {}) {
    const ghost = opts.ghost;
    const hi = Math.max(you, market, ghost || 0) * 1.12 || 1;
    const norm = opts.scale === "sqrt"
      ? (v) => Math.sqrt(Math.max(v, 0)) / Math.sqrt(hi)
      : (v) => v / hi;
    const px = (v) => clamp(norm(v), 0, 1) * 100;
    return h("div.dumb", { "aria-hidden": "true" },
      h("i.dumb__track"),
      ghost === undefined || ghost === null ? null
        : h("i.dumb__ghost", { style: { left: `${px(ghost)}%` } }),
      h("i.dumb__line", { style: { left: `${Math.min(px(you), px(market))}%`,
                                   width: `${Math.abs(px(you) - px(market))}%` } }),
      h("i.dumb__mkt", { style: { left: `${px(market)}%` } }),
      h("i.dumb__you", { style: { left: `${px(you)}%` } }));
  }

  /** One earned/max hairline bar. The track IS the max, so no bar is zero-width. */
  function hairlineBar(earned, max) {
    const f = clamp(max ? earned / max : 0, 0, 1);
    return h("div.hbar", { "aria-hidden": "true" },
      h("i.hbar__fill", { style: { width: `${f * 100}%` } }));
  }

  /**
   * Labelled segments over one track. Each segment owns its share of the WIDTH
   * (the weight) and fills to its own value — so the eye reads which side of a
   * weighted blend is carrying the number. Deliberately not a gauge.
   * @param {Array<{width:number, fill:number, tone?:string}>} segs
   */
  function segmentTrack(segs) {
    return h("div.segtrack", { "aria-hidden": "true" },
      segs.map((sg) => h(`i.segtrack__seg${sg.tone ? "." + sg.tone : ""}`, {
        style: { width: `${sg.width * 100}%`, "--fill": `${clamp(sg.fill, 0, 1) * 100}%` },
      })));
  }

  /**
   * Filament — a hairline track with a lit segment. Used where the POINT is how
   * little is lit (27 of the 34 clinics have never appeared as an ad).
   */
  function filament(fraction, opts = {}) {
    const el = h("div.filament", { style: { color: opts.color || "" } },
      h("div.filament__fill", {
        style: { width: `${clamp(fraction, 0, 1) * 100}%` },
      }));
    if (opts.title) el.title = opts.title;
    return el;
  }

  /** A dose gauge — six cells, lit in proportion to the points a fix is worth. */
  function doseGauge(lift, opts = {}) {
    const cells = 6, lit = clamp(Math.round(lift / 5), 1, cells);
    const w = opts.width || 12, cellH = opts.cell || 7, height = cells * cellH;
    const bars = [];
    for (let i = 0; i < cells; i++) {
      bars.push(s("rect", { x: 0, y: height - (i + 1) * cellH + 1.5, width: w,
                            height: cellH - 3, rx: 1.5,
                            class: i < lit ? "dose dose--lit" : "dose" }));
    }
    return s("svg", { class: "viz", viewBox: `0 0 ${w} ${height}`, width: w, height,
                      "aria-hidden": "true" }, bars);
  }

  /**
   * Six-spoke polar. Hand-drawn, never an ECharts radar: a category the clinic
   * never appears in renders as a DEAD STUB rather than a zero-length spoke that
   * looks like data.
   * Radius is INVERTED position — #1 sits outermost.
   */
  function polar(cats, market, mine, opts = {}) {
    const size = opts.size || 240;
    const cx = size / 2, cy = size / 2, R = opts.radius || Math.round(size * 0.29);
    const labelR = opts.labelR || R + 24;
    const rOf = (pos) => R * clamp((15 - pos) / 14, 0.08, 1);
    const ang = (i) => (Math.PI * 2 * i) / cats.length - Math.PI / 2;

    const kids = [];
    for (const f of [0.33, 0.66, 1]) {
      kids.push(s("circle", { cx, cy, r: (R * f).toFixed(1), class: "hair", fill: "none" }));
    }
    const mkt = cats.map((cat, i) => {
      const r = rOf(market[cat]);
      return [cx + r * Math.cos(ang(i)), cy + r * Math.sin(ang(i))];
    });
    kids.push(s("polygon", { class: "polar-mkt",
      points: mkt.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ") }));

    const pts = [], vertices = [], stubs = [];
    cats.forEach((cat, i) => {
      const entry = mine.get(cat);
      const a = ang(i);
      if (entry) {
        const r = rOf(entry.pos);
        const x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
        pts.push([x, y]);
        vertices.push(s("circle", {
          cx: x.toFixed(1), cy: y.toFixed(1),
          r: (2.6 + Math.min(3.4, Math.sqrt(entry.n))).toFixed(1), class: "polar-vertex",
        }, s("title", {}, `${cat} · your average #${entry.pos} from ${entry.n} appearances · market #${market[cat]}`)));
      } else {
        const r0 = R * 0.1, r1 = R * 0.22;
        stubs.push(s("line", {
          x1: (cx + r0 * Math.cos(a)).toFixed(1), y1: (cy + r0 * Math.sin(a)).toFixed(1),
          x2: (cx + r1 * Math.cos(a)).toFixed(1), y2: (cy + r1 * Math.sin(a)).toFixed(1),
          class: "polar-stub",
        }, s("title", {}, `${cat} — you never appear here`)));
      }
      kids.push(s("line", { x1: cx, y1: cy, x2: cx + R * Math.cos(a), y2: cy + R * Math.sin(a),
                            class: "hair" }));
      const lx = cx + labelR * Math.cos(a), ly = cy + labelR * Math.sin(a);
      kids.push(s("text", {
        x: lx.toFixed(1), y: ly.toFixed(1),
        "text-anchor": Math.abs(Math.cos(a)) < 0.3 ? "middle" : (Math.cos(a) > 0 ? "start" : "end"),
        "dominant-baseline": "middle", class: "polar-label",
      }, short(cat.replace(" & Social Proof", "").replace(" & Booking", ""), 13)));
    });

    // Two points cannot make a polygon and one cannot make a line; both degrade
    // to the marks themselves rather than to nothing.
    if (pts.length >= 3) {
      kids.push(s("polygon", { class: "polar-you",
        points: pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ") }));
    } else if (pts.length === 2) {
      kids.push(s("line", { class: "polar-you-line",
        x1: pts[0][0].toFixed(1), y1: pts[0][1].toFixed(1),
        x2: pts[1][0].toFixed(1), y2: pts[1][1].toFixed(1) }));
    }
    kids.push(...stubs, ...vertices);

    return s("svg", {
      class: "viz polar", viewBox: `0 0 ${size} ${size}`,
      role: "img", "aria-label": opts.ariaLabel || "Average search position by patient intent",
    }, kids);
  }

  /**
   * Mini dot-map. Normalised lat/lng with distance rings from the city core —
   * no tiles, no network, no <img>, ~0 KB.
   * @param {Array<{key,lat,lng,band,title,you,out}>} pts
   */
  function miniMap(pts, opts = {}) {
    const w = opts.width || 300, hgt = opts.height || 300, pad = opts.pad || 22;
    if (!pts.length) return null;
    const lats = pts.map((p) => p.lat), lngs = pts.map((p) => p.lng);
    const lat0 = Math.min(...lats), lat1 = Math.max(...lats);
    const lng0 = Math.min(...lngs), lng1 = Math.max(...lngs);
    const X = (lng) => pad + ((lng - lng0) / ((lng1 - lng0) || 1)) * (w - pad * 2);
    // Latitude increases northward but SVG y increases downward, so invert.
    const Y = (lat) => hgt - pad - ((lat - lat0) / ((lat1 - lat0) || 1)) * (hgt - pad * 2);

    const core = opts.core || [16.3067, 80.4365];
    const cx = X(core[1]), cy = Y(core[0]);
    const kmPx = Math.abs(X(core[1] + 1 / 106.6) - cx);

    const kids = [];
    for (const km of (opts.rings || [1, 2])) {
      kids.push(s("circle", { cx, cy, r: (kmPx * km).toFixed(1), class: "map-ring", fill: "none" }));
      if (opts.ringLabels !== false) {
        kids.push(s("text", { x: (cx + kmPx * km + 3).toFixed(1), y: (cy - 3).toFixed(1),
                              class: "map-km" }, `${km} km`));
      }
    }
    kids.push(s("circle", { cx, cy, r: opts.coreR || 4, class: "map-core" }));

    for (const p of pts) {
      kids.push(s("circle", {
        cx: X(p.lng).toFixed(1), cy: Y(p.lat).toFixed(1),
        r: p.you ? (opts.youR || 7) : (opts.dotR || 5),
        class: `map-dot map-dot--${p.band}` + (p.you ? " is-you" : "") + (p.out ? " is-out" : ""),
        data: opts.keyed === false ? null : { clinic: p.key },
      }, p.title ? s("title", {}, p.title) : null));
    }

    return s("svg", { class: "viz map", viewBox: `0 0 ${w} ${hgt}`,
                      preserveAspectRatio: opts.preserve || "xMidYMid meet",
                      role: "img",
                      "aria-label": opts.ariaLabel || "Clinic locations around the city core" },
             kids);
  }

  /**
   * Mesh jewel. `family` selects the recipe; for the visibility hero it comes
   * from the score band, so the colour drains of green as the score falls.
   * `register: "light"` puts the hero on the display-light face — the atlas's
   * one sanctioned exception, for an INDEX (a rank is a span, not a count).
   */
  function jewel({ family, label, value, sub, viz, ariaLabel, register, unit }) {
    const hero = register === "light"
      ? h("div.j-hero", { "aria-hidden": "true" },
          h("span.disp.j-disp", { text: String(value) }),
          unit ? h("span.j-unit", { text: unit }) : null)
      : h("div.dot-num.dot-num--white", { text: String(value), "aria-hidden": "true" });
    return h(`div.jewel.jewel--${family}`, {
      role: "img", "aria-label": ariaLabel || `${label}: ${value}. ${sub || ""}`,
    },
      h("div.j-label", { text: label }),
      hero,
      sub ? h("div.j-sub", { text: sub }) : null,
      viz ? h("div.j-viz", { "aria-hidden": "true" }, viz) : null);
  }

  /** A naked metric: dot-matrix numeral + attached label pill + caption. */
  function metric({ value, pill: pillText, caption, lime, register = "dot", unit }) {
    const numEl = register === "light"
      ? h("span.disp", { text: String(value) })
      : h("span.dot-num", { text: String(value) });
    return h("div.metric",
      h("div.metric__top", numEl,
        unit ? h("span.unit", { text: unit }) : null,
        pillText ? h("span.pill" + (lime ? ".pill--lime" : ""), { text: pillText }) : null),
      caption ? h("div.metric__c", { text: caption }) : null);
  }

  /** A pill. `tone` is one of lime | warn | quiet; anything else is the default. */
  function pill(text, tone) {
    return h("span.pill" + (tone ? `.pill--${tone}` : ""), { text: String(text) });
  }

  /** A labelled row of pills, with an explicit empty line rather than a blank. */
  function pillRow(label, items, tone, emptyText) {
    const row = h("div.pillrow", h("span.pillrow__k", { text: label }));
    if ((items || []).length) {
      items.forEach((t) => row.append(pill(t, tone)));
    } else {
      row.append(h("span.pillrow__none", { text: emptyText || "nothing here" }));
    }
    return row;
  }

  /**
   * The span idiom — `#26 → #9`. A rank is a position, so both terminals ride
   * the display-light register; `size` picks the step (xs | sm | md).
   */
  function deltaSpan(from, to, opts = {}) {
    const cls = opts.size ? `.disp--${opts.size}` : "";
    return h("div.dspan",
      h(`span.disp${cls}`, { text: String(from) }),
      h("span.dspan__arrow", { text: "→", "aria-hidden": "true" }),
      h(`span.disp${cls}.dspan__to`, { text: String(to) }),
      opts.unit ? h("span.unit", { text: opts.unit }) : null);
  }

  /**
   * Edge-crop wrapper. The verifier reads the crop's PARENT computed overflow,
   * so the wrapper is the compliance, not a convenience — a bare .edge-crop
   * dropped into a panel body fails law 7 even though the card itself clips.
   */
  function edgeCrop(node, opts = {}) {
    return h(`div.crop.yc-crop${opts.class ? "." + opts.class : ""}`,
      h("div.edge-crop", { "aria-hidden": "true" }, node));
  }

  /** Segmented stepper. Not a <select> — the design laws ban those outright. */
  function stepper(items, current, onPick, opts = {}) {
    const el = h("div.seg.yc-stepper", { role: "group", "aria-label": opts.label || "Choose" });
    items.forEach((it) => {
      el.append(h("button", {
        type: "button", text: short(it.label, opts.chars || 24), title: it.label,
        "aria-pressed": String(it.value === current),
        onclick: () => onPick(it.value),
      }));
    });
    return el;
  }

  /* Presentation copy for the platform slugs the web dataset carries. Python's
     report._PLATFORM_LABEL is the only other place these are spelled out, and
     it never reaches the browser. */
  const PLATFORM_LABEL = {
    justdial: "JustDial", practo: "Practo", lybrate: "Lybrate", sulekha: "Sulekha",
    youtube: "YouTube", instagram: "Instagram", facebook: "Facebook",
    twitter: "X", linkedin: "LinkedIn", clinic_site: "Own site",
  };
  const platformLabel = (slug) => PLATFORM_LABEL[slug]
    || String(slug || "").replace(/[_-]+/g, " ").replace(/^./, (m) => m.toUpperCase());

  /**
   * The JS twin of build_web._display_name. Google Maps names are keyword
   * stuffed ("Name / Dermatologist / Best skin clinic ..."); the payload carries
   * a cleaned `display_name` for its own clinics, but SERP and proof strings
   * arrive raw and would otherwise land 125 characters wide in a 336px column.
   */
  function displayName(raw) {
    const n = String(raw || "").trim();
    const first = n.split(/\s*[/|]\s*/)[0].replace(/^[\s\-–·]+|[\s\-–·]+$/g, "");
    return first.length >= 4 ? first : n;
  }

  /**
   * Cross-filter highlight for DOM/SVG panels. One pass over the root, never a
   * per-node query storm and never a re-render.
   */
  function hilite(root, key) {
    if (!root) return;
    root.querySelectorAll(".is-hot").forEach((n) => n.classList.remove("is-hot"));
    if (!key) return;
    root.querySelectorAll(`[data-clinic="${CSS.escape(key)}"]`)
      .forEach((n) => n.classList.add("is-hot"));
  }

  /** Mark filtered-out marks so the distribution's shape survives a filter. */
  function applyFilterClass(root, keys) {
    if (!root) return;
    root.querySelectorAll("[data-clinic]").forEach((n) => {
      n.classList.toggle("is-out", !!keys && !keys.has(n.dataset.clinic));
    });
  }

  DI.inst = {
    // v3 exports — 85-panels-market.js depends on these signatures.
    tickRuler, dotColumn, filament, jewel, metric, hilite, applyFilterClass, rand,
    // v4 additions.
    pointRuler, spanRuler, dotCensus, dotMeter, jitterGrid, dumbbell, hairlineBar,
    segmentTrack, doseGauge, polar, miniMap, pill, pillRow, deltaSpan, edgeCrop,
    stepper, platformLabel, displayName,
  };
})(window.DI);
