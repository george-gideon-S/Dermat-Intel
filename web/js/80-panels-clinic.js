/* ── "Your Clinic" panels ──────────────────────────────────────────────────── */
(function (DI) {
  "use strict";

  const { h, inst, store, bus, app } = DI;

  /* ── P1 · Twin jewels ───────────────────────────────────────────────────────
     The locked hero. The visibility jewel STATE-MAPS: its recipe follows the
     score band, so a 34 renders in caution and can never read as reassuring.
     The rank jewel never state-maps — a rank is an index, not a condition.

     The dot column is not decoration: hovering a bar cross-filters the whole
     canvas, which is what turns the hero from a picture into a control. */
  app.register({
    id: "twin-jewels",
    page: "clinic",
    span: 7,
    card: false,
    subject: true,
    title: null,

    mount(body, ctx) {
      const wrap = h("div.jewel-pair");
      body.append(wrap);
      const api = { wrap };
      draw(api, ctx);

      // Hovering a column in the distribution highlights that clinic everywhere.
      wrap.addEventListener("pointermove", (e) => {
        const node = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(node ? node.dataset.clinic : null, "twin-jewels");
      });
      wrap.addEventListener("pointerleave", () => bus.hover(null, "twin-jewels"));
      wrap.addEventListener("click", (e) => {
        const node = e.target.closest && e.target.closest("[data-clinic]");
        if (node && store.select(node.dataset.clinic)) bus.emit("select", { key: node.dataset.clinic });
      });
      return api;
    },

    update(api, ctx) { draw(api, ctx); },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  function draw(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const all = ctx.all;
    // The distribution is the whole market, sorted, with the subject lit.
    const sorted = all.slice().sort((a, b) => (a.visibility || 0) - (b.visibility || 0));
    const values = sorted.map((x) => x.visibility || 0);
    const keys = sorted.map((x) => x.key);
    const idx = keys.indexOf(c.key);

    const band = store.bandOf(c.visibility);
    const total = c.visibility_total || all.length;

    api.wrap.textContent = "";
    api.wrap.append(
      inst.jewel({
        family: band,
        label: "Online visibility",
        value: c.visibility,
        sub: `${bandLabel(band)} · ${c.visibility_rank} of ${total} in Guntur`,
        viz: inst.dotColumn(values, { highlight: idx, keys, height: 46 }),
        ariaLabel: `Online visibility ${c.visibility} out of 100, ranked ${c.visibility_rank} of ${total}.`,
      }),
      inst.jewel({
        family: "index",
        label: "Market rank",
        value: c.visibility_rank,
        sub: `of ${total} in Guntur`,
        viz: inst.tickRuler(total, (c.visibility_rank - 1) / Math.max(1, total - 1), { height: 26 }),
        ariaLabel: `Ranked ${c.visibility_rank} of ${total} clinics in Guntur.`,
      }));
  }

  function bandLabel(band) {
    return { alarm: "Nearly invisible", caution: "Below market",
             steady: "Partway there", clear: "Strong" }[band] || "";
  }
})(window.DI);
