/* ── Instruments ──────────────────────────────────────────────────────────────
   Hand-authored SVG. These are the components that make the dashboard read as an
   instrument rather than a chart library: tick rulers with one glowing marker,
   dot columns that shimmer, filaments that show emptiness, and the mesh jewels.

   Two rules from the atlas are enforced here rather than left to callers:
     * rulers are QUOTA-FREE — there is no target line, ever;
     * jitter is SEEDED — Math.random() is banned so verifier shots reproduce. */
(function (DI) {
  "use strict";

  const { s, h, clamp, rand } = DI;

  /**
   * Tick ruler. Ticks at 45% alpha, major every 6th, and exactly one full-alpha
   * marker carrying a glow. That contrast is what separates "instrument" from
   * "bar chart".
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
   * Filament — a hairline track with a lit segment. Used where the POINT is how
   * little is lit (31 of 34 clinics have never bought an ad).
   */
  function filament(fraction, opts = {}) {
    const el = h("div.filament", { style: { color: opts.color || "" } },
      h("div.filament__fill", {
        style: { width: `${clamp(fraction, 0, 1) * 100}%` },
      }));
    if (opts.title) el.title = opts.title;
    return el;
  }

  /**
   * Mesh jewel. `family` selects the recipe; for the visibility hero it comes
   * from the score band, so the colour drains of green as the score falls.
   */
  function jewel({ family, label, value, sub, viz, ariaLabel }) {
    return h(`div.jewel.jewel--${family}`, {
      role: "img", "aria-label": ariaLabel || `${label}: ${value}. ${sub || ""}`,
    },
      h("div.j-label", { text: label }),
      h("div.dot-num.dot-num--white", { text: String(value), "aria-hidden": "true" }),
      sub ? h("div.j-sub", { text: sub }) : null,
      viz ? h("div.j-viz", { "aria-hidden": "true" }, viz) : null);
  }

  /** A naked metric: dot-matrix numeral + attached label pill + caption. */
  function metric({ value, pill, caption, lime, register = "dot", unit }) {
    const numEl = register === "light"
      ? h("span.disp", { text: String(value) })
      : h("span.dot-num", { text: String(value) });
    return h("div.metric",
      h("div.metric__top", numEl,
        unit ? h("span.unit", { text: unit }) : null,
        pill ? h("span.pill" + (lime ? ".pill--lime" : ""), { text: pill }) : null),
      caption ? h("div.metric__c", { text: caption }) : null);
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

  DI.inst = { tickRuler, dotColumn, filament, jewel, metric, hilite, applyFilterClass, rand };
})(window.DI);
