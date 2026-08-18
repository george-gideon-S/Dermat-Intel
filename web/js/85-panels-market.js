/* ── "The Market" — the sixteen v4 cards ───────────────────────────────────────
   Contract: docs/redesign/v4/V0_CARD_INVENTORY.md §4. Registration order IS DOM
   order IS reading order, so the bento comes out as approved:

     A  01 the map (square)  ·  02 pulse + 03 nobody's ground + 04 mirage (half ×3)
     B  05 organic · 06 ads nobody runs · 07 review economy · 08 four bands (stat ×4)
     C  09 opportunity map · 10 visibility league                    (square ×2)
     D  11 who owns the results                                      (band)
     E  12 own vs borrowed · 13 who pays for the page                (square ×2)
     F  14 how far the market gets · 15 demand & depth               (half ×2)
     G  16 every clinic                                              (band)

   Row A tiles exactly: the map is 6c × 6r and the three `half` cards beside it
   are 2 rows each. The map is NOT the inventory's 12×4 hero — the Guntur bbox is
   PORTRAIT (viewBox 1000×1041) and the 34 clinics use nearly all of it, so
   cover-cropping a 1392×432 band was measured to drop pins at every height.

   Four rules this file is built around:

   1. **Mount once.** mount() builds the DOM/chart and returns a handle; update()
      patches through it. Nothing is re-parented, nothing is re-mounted, and
      highlight() never calls setOption.
   2. **The filter is the expensive channel.** Six cards consume it and every one
      of them dims in a single `inst.applyFilterClass` pass over a node list
      cached at mount. The eleven static aggregates declare no update() at all,
      or guard it on the subject — `updateAll({force:true})` runs every panel on
      the page for both `select` and `filter`.
   3. **The dot register is retired on this page except the jewel hero.** Doto
      measures 2–5% ink coverage on the light field against display-light's 69%
      (ATLAS-DARK.md §7), so every numeral here is `.disp` or Geist Mono. The one
      `.dot-num` is MK-02's dot-white jewel hero, exactly as the clinic page keeps
      exactly one.
   4. **Censuses.** One jewel (MK-02). Two limes (MK-03's featured pill, MK-01a's
      live readout while a filter is active). Band chroma outside the jewel lives
      on MK-01's pins and MK-08's dot runs and nowhere else — every subject
      marker that was lime in v3 is `--ink-1` here. */
(function (DI) {
  "use strict";

  const { h, s, inst, store, bus, app, charts, P, num, short, clamp, median } = DI;

  /* The three denominators, kept straight (inventory §6): 50 Maps queries · 78
     captured result pages · 80 searches total. */
  const serpOwn = (D) => ((D.serp || {}).ownership) || null;
  const serpQueries = (D) => ((serpOwn(D) || {}).totals || {}).queries || 78;

  const BAND_LABEL = { alarm: "Nearly invisible", caution: "Below market",
                       steady: "Partway there", clear: "Strong" };

  /* The map card's projection. Equirectangular, and byte-identical to
     web/maps.py::project — the bbox and the viewBox travel in the payload
     precisely so this cannot drift (tests/test_geo_payload.py pins the pair).
     v3 auto-fitted to the clinic cloud's own extents, which put the pins in a
     coordinate space unrelated to the SVG they were drawn over. */
  const FALLBACK_GEO = { bbox: [16.28, 80.41, 16.33, 80.46], view: [1000, 1041] };

  function project(lat, lng, geo) {
    const [s0, w, n, e] = geo.bbox;
    const [vw, vh] = geo.view;
    return [(lng - w) / (e - w) * vw, (n - lat) / (n - s0) * vh];
  }

  /** Hide a whole card. `[hidden]` is only display:none at UA level and .panel
   *  sets display:flex; the real rule ships with the clinic sheet. */
  function setShown(api, on) {
    if (api.panel) api.panel.hidden = !on;
    return on;
  }

  /** A card that only moves when the SUBJECT moves. Both bus channels force a
   *  full page patch, so without this guard eleven aggregates would redraw on
   *  every brush and produce exactly the same pixels. */
  function subjectChanged(api, ctx) {
    const key = ctx.subject ? ctx.subject.key : "";
    if (api._subj === key) return false;
    api._subj = key;
    return true;
  }

  /* ═══ MK-01 · The Guntur map ══════════════════════════════════════════════════
     The page's one geographic surface, and its busiest one: filter SOURCE (seven
     pills), filter CONSUMER (pins dim), select SOURCE (pin click), and the host
     of MK-01a's KPI tiles and MK-01b's pop-card.

     Two SVGs share one box and one viewBox, so the pins land on the roads: the
     styled geometry cloned from <template id="di-mapcard"> underneath, a pin
     layer over it. Neither is scaled independently — both are
     preserveAspectRatio="xMidYMid meet" on 0 0 1000 1041. */
  app.register({
    id: "mk01-map", page: "market", size: "square",
    title: "The Guntur market", sub: "34 clinics · colour is online standing",

    mount(body, ctx, slots) {
      const stage = h("div.mk-stage");
      const geo = h("div.mk-stage__geo", { "aria-hidden": "true" });
      const tpl = document.getElementById("di-mapcard");
      // No <img>, no fetch, no innerHTML — the geometry arrives as markup the
      // build inlined, and the card takes a copy of it.
      if (tpl && tpl.content) geo.append(tpl.content.cloneNode(true));

      const pins = s("svg", {
        class: "viz mk-pins", viewBox: "0 0 1000 1041",
        preserveAspectRatio: "xMidYMid meet", role: "img",
        "aria-label": "Every clinic we read, placed on Guntur and coloured by online standing",
      });
      const rail = h("div.mk-pills", { role: "group", "aria-label": "Filter the market" });
      const tiles = h("div.mk-tiles");
      stage.append(geo, pins, rail, tiles);

      const note = h("p.caveat");
      body.append(stage, note);

      const api = { stage, pins, rail, tiles, note, panel: slots.panel,
                    pinEls: new Map(), pillEls: [], pop: null, popKey: null, hot: null };
      buildPins(api, ctx);
      buildPills(api, ctx);
      drawTiles(api, ctx);

      // ONE delegated handler per gesture. Per-pin listeners would be 102 of
      // them and would put the hover contract straight through its 0.2 ms floor.
      stage.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest(".pin[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "mk01-map");
      });
      stage.addEventListener("pointerleave", () => bus.hover(null, "mk01-map"));
      stage.addEventListener("click", (e) => {
        if (e.target.closest(".mk-pills") || e.target.closest(".mk-tiles")
            || e.target.closest(".mk-pop")) return;
        const n = e.target.closest && e.target.closest(".pin[data-clinic]");
        if (!n) { closePin(api); return; }
        const key = n.dataset.clinic;
        // A second click on the same pin dismisses, which is what makes the
        // pop-card feel like a toggle rather than a modal.
        if (api.popKey === key) { closePin(api); return; }
        if (store.select(key)) bus.emit("select", { key });
        openPin(api, key, n);
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && api.pop) { e.stopPropagation(); closePin(api); }
      });
      return api;
    },

    update(api, ctx) {
      // One pass. Never a rebuild — the 34 pins are built once and only their
      // classes move afterwards.
      inst.applyFilterClass(api.pins, ctx.keys);
      const key = ctx.subject ? ctx.subject.key : null;
      if (api.youKey !== key) {
        const was = api.youKey && api.pinEls.get(api.youKey);
        if (was) was.classList.remove("is-you");
        const now = key && api.pinEls.get(key);
        if (now) now.classList.add("is-you");
        api.youKey = key;
      }
      syncPills(api);
      drawTiles(api, ctx);
    },

    highlight(api, key) {
      if (api.hot === key) return;
      const was = api.hot && api.pinEls.get(api.hot);
      if (was) was.classList.remove("is-hot");
      const now = key && api.pinEls.get(key);
      if (now) now.classList.add("is-hot");
      api.hot = key || null;
    },
  });

  function buildPins(api, ctx) {
    const geo = ctx.D.geo || FALLBACK_GEO;
    const pts = ctx.all.filter((c) => c.lat !== null && c.lng !== null
                                   && c.lat !== undefined && c.lng !== undefined);
    // Several Guntur clinics share a building. A collided pin is nudged rather
    // than hidden, and the nudge is SEEDED off the clinic key — Math.random is
    // banned so a verifier screenshot reproduces byte for byte.
    const used = new Map();
    api.pins.textContent = "";
    api.pinEls.clear();
    for (const c of pts) {
      let [x, y] = project(c.lat, c.lng, geo);
      const cell = `${Math.round(x / 15)}:${Math.round(y / 15)}`;
      const n = used.get(cell) || 0;
      used.set(cell, n + 1);
      if (n) {
        x += (inst.rand(`${c.key}·px`) - 0.5) * 24;
        y += (inst.rand(`${c.key}·py`) - 0.5) * 24;
      }
      const band = store.bandOf(c.visibility);
      const cx = x.toFixed(1), cy = y.toFixed(1);
      const g = s("g", { class: `pin pin--${band}`, data: { clinic: c.key } },
        s("circle", { class: "pin__halo", cx, cy, r: 16 }),
        s("circle", { class: "pin__core", cx, cy, r: 5.4 }),
        s("title", {}, `${c.display_name} · visibility ${c.visibility} · ${BAND_LABEL[band]}`));
      api.pins.append(g);
      api.pinEls.set(c.key, g);
    }
    api.note.textContent = pts.length === ctx.all.length
      ? `Every one of the ${ctx.all.length} clinics we read, on its real coordinates. `
        + "Colour is the visibility band; a pin that shares a building is nudged to stay countable."
      : `${pts.length} of ${ctx.all.length} clinics located — the rest have no coordinates yet.`;
  }

  /* The seven pills are the entire surviving filter UI from the deleted 250px
     rail: band ×4 and presence ×3. The verdict facet was killed outright and the
     ads flag moved to MK-13's header. */
  function buildPills(api, ctx) {
    const f = ctx.D.facets || {};
    api.rail.textContent = "";
    api.pillEls = [];
    const add = (facet) => (item) => {
      const b = inst.togglePill({
        label: item.label, count: item.count,
        pressed: store.state.filter[facet].has(item.key),
        title: `${item.label} — ${item.count} of ${ctx.all.length} clinics`,
        onclick: () => { store.toggleFacet(facet, item.key); bus.emit("filter", {}); },
      });
      api.rail.append(b);
      api.pillEls.push([facet, item.key, b]);
    };
    (f.band || []).forEach(add("band"));
    (f.presence || []).forEach(add("presence"));
  }

  /** Counts on the pills are CORPUS counts and never move; only pressed does. */
  function syncPills(api) {
    for (const [facet, key, b] of api.pillEls) {
      b.setAttribute("aria-pressed", String(store.state.filter[facet].has(key)));
    }
  }

  /* ═══ MK-01a · KPI tile trio (on-map, dark) ═══════════════════════════════════
     Tile 1 is the page's live filter readout AND its only filter reset. The lime
     pill and the clickability appear and disappear together, which is what makes
     the readout legible as STATE rather than decoration.

     Tiles 2 and 3 are corpus aggregates and deliberately do not follow the
     filter — tile 1 being the one that moves is the whole point. */
  function drawTiles(api, ctx) {
    const f = ctx.D.facets || {}, k = ctx.D.kpis || {};
    const inv = (f.presence || []).find((p) => p.key === "invisible");
    api.tiles.textContent = "";
    api.tiles.append(
      inst.tile({
        value: ctx.filtered.length,
        pill: ctx.active ? `of ${ctx.all.length}` : null,
        lime: ctx.active, live: true,
        caption: ctx.active ? "clinics in view · click to clear" : "clinics mapped in Guntur",
        ariaLabel: ctx.active
          ? `${ctx.filtered.length} of ${ctx.all.length} clinics in view. Clear every filter.`
          : `${ctx.all.length} clinics mapped in Guntur.`,
        // Never disabled at zero: a brush and a pill compose to an empty market,
        // and this tile is the only way back out of it.
        onclick: ctx.active ? () => { store.clearFilters(); bus.emit("filter", {}); } : null,
      }),
      inst.tile({ value: inv ? inv.count : "—", caption: "invisible in Google search" }),
      inst.tile({ value: k.median_reviews === undefined || k.median_reviews === null
                    ? "—" : num(k.median_reviews),
                  caption: "median reviews" }));
  }

  /* ═══ MK-01b · Pin pop-card ═══════════════════════════════════════════════════
     EXACTLY six fields, fixed by the plan's privacy decision: name, visibility,
     rank, reviews, rating, has-website. No plan, no breakdown, no scorecard, no
     address or phone. This and nothing else on the page may show `rating`.

     Created and destroyed rather than kept hidden — a hidden Float layer still
     costs a compositing layer over the map. */
  function closePin(api) {
    if (api.popAway) document.removeEventListener("pointerdown", api.popAway, true);
    api.popAway = null;
    if (api.pop) api.pop.remove();
    api.pop = null;
    api.popKey = null;
  }

  function openPin(api, key, pinEl) {
    closePin(api);
    const c = DI.byKey.get(key);
    if (!c) return;
    const band = store.bandOf(c.visibility);
    const isSubject = store.state.selected === c.key;

    const card = h("div.mk-pop.g-float", {
      role: "dialog", "aria-label": `${c.display_name} — summary`,
    });
    card.append(h("div.mk-pop__h",
      h(`i.mk-pop__dot.mk-dot--${band}`, { "aria-hidden": "true" }),
      h("span.mk-pop__n", { text: short(c.display_name, 54), title: c.display_name })));

    const grid = h("div.mk-pop__g");
    const row = (label, value) => {
      grid.append(h("span.mk-pop__k", { text: label }), h("span.mk-pop__v", value));
    };
    row("Visibility", h("span.mk-pop__vis",
      h("span.disp.disp--xs", { text: String(c.visibility) }),
      h("i.mk-pop__track", h("i", { style: { width: `${clamp(c.visibility || 0, 0, 100)}%` } }))));
    row("Rank", h("span.disp.disp--xs",
      { text: `#${c.visibility_rank} / ${c.visibility_total || 34}` }));
    row("Reviews", h("span.mk-mono", { text: num(c.reviews) }));
    row("Rating", h("span.disp.disp--xs",
      { text: c.rating === null || c.rating === undefined ? "—" : c.rating.toFixed(1) }));
    row("Website", inst.twoState(!!c.has_website,
      { onTitle: "lists a website on Maps", offTitle: "no website listed",
        onLabel: "lists a website", offLabel: "no website" }));
    card.append(grid);

    card.append(h("button.mk-pop__go", {
      type: "button",
      // store.select returns false for an UNCHANGED key, so the navigation must
      // not be gated on it — that is a live bug shape in v3's table row handler.
      text: isSubject ? "Open the report ↗" : "Open this clinic's report ↗",
      onclick: () => {
        if (store.select(c.key)) bus.emit("select", { key: c.key });
        closePin(api);
        app.go("clinic");
      },
    }));

    api.stage.append(card);
    api.pop = card;
    api.popKey = key;
    placePin(api, card, pinEl);

    // Dismiss on any pointerdown outside. Registered on the next frame so the
    // click that opened the card does not immediately close it.
    requestAnimationFrame(() => {
      if (!api.pop || api.popKey !== key) return;
      api.popAway = (e) => {
        if (api.pop && !api.pop.contains(e.target)) closePin(api);
      };
      document.addEventListener("pointerdown", api.popAway, true);
    });
  }

  /** Anchored to the pin, flipped when it would leave the stage. */
  function placePin(api, card, pinEl) {
    const sb = api.stage.getBoundingClientRect();
    const pb = pinEl.getBoundingClientRect();
    const w = card.offsetWidth, hh = card.offsetHeight;
    const ax = pb.left - sb.left + pb.width / 2;
    const ay = pb.top - sb.top + pb.height / 2;
    let left = ax + 12;
    let top = ay + 12;
    if (left + w > sb.width - 4) left = ax - w - 12;
    if (top + hh > sb.height - 4) top = ay - hh - 12;
    card.style.left = `${Math.max(4, Math.min(left, sb.width - w - 4))}px`;
    card.style.top = `${Math.max(4, Math.min(top, sb.height - hh - 4))}px`;
  }

  /* ═══ MK-02 · Market pulse jewel ══════════════════════════════════════════════
     The page's ONE jewel. The family is derived, never authored: invert the
     invisible share into a visible share and run it through the same band
     thresholds every other surface uses — bandOf(41) is `caution`.

     Static, which REVERSES v3 (its market jewel followed the filter). The
     sub-line names the corpus denominator in every state so that "5 of 34 in
     view" on the map and "20 invisible of 34" here cannot read as a bug. */
  app.register({
    id: "mk02-pulse", page: "market", size: "half", aria: "Market pulse",

    mount(body, ctx) {
      const host = h("div.mk-jewelhost");
      body.append(host);
      const f = ctx.D.facets || {};
      const inv = (f.presence || []).find((p) => p.key === "invisible");
      const total = f.total || ctx.all.length;
      if (!inv || !total) {
        host.append(h("p.panel__note", { text: "Web presence not yet read." }));
        return { host };
      }
      const pct = Math.round((inv.count / total) * 100);
      host.append(inst.jewel({
        family: store.bandOf(Math.round(100 * (1 - inv.count / total))),
        label: "Invisible in Google search",
        value: inv.count,
        sub: `of ${total} clinics · ${pct}% of the market`,
        viz: inst.dotCensus(total, { lit: inv.count, per: total, cell: 7, r: 2.2, scale: 1.1 }),
        ariaLabel: `${inv.count} of ${total} clinics are invisible in Google search.`,
      }));
      return { host };
    },
  });

  /* ═══ MK-03 · Nobody's ground ═════════════════════════════════════════════════
     Half the market's search real estate belongs to no local clinic. Featured
     lime pill №1 — and the meter beside it stays neutral, because a lime chart
     fill is banned outright. */
  app.register({
    id: "mk03-nobody", page: "market", size: "half", title: "Nobody's ground",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const own = serpOwn(ctx.D);
      const t = own && own.totals;
      const api = { wrap, panel: slots.panel };
      // serp_ownership([]) returns blocks:0, so the guard is on the count and
      // not on the object — otherwise the card renders "0 of 0".
      if (!setShown(api, !!(t && t.blocks))) return api;

      wrap.append(h("div.mk-hero",
        h("span.disp.disp--md", { text: num(t.unmapped) }),
        h("span.pill.pill--lime", { text: `of ${num(t.blocks)}` })));
      wrap.append(h("p.metric__c", {
        text: `result blocks across ${t.queries} result pages belong to no clinic in Guntur.`,
      }));
      wrap.append(inst.shareMeter(t.mapped / t.blocks, {
        leftTitle: `${num(t.mapped)} local`, rightTitle: `${num(t.unmapped)} not local`,
      }));
      wrap.append(h("p.caveat", {
        text: `${num(t.mapped)} local · ${num(t.unmapped)} not local.`,
      }));
      return api;
    },
  });

  /* ═══ MK-04 · The website mirage ══════════════════════════════════════════════
     Twenty clinics list a website on Maps; ten actually rank with one. The card
     exists to defend the presence doctrine ("a paid placement is OWNED") against
     the obvious objection — it is the one place the 20 / 12 / 10 / 2 arithmetic
     is shown rather than asserted. */
  app.register({
    id: "mk04-mirage", page: "market", size: "half", title: "The website mirage",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap, panel: slots.panel };
      if (!setShown(api, ctx.D.web_available !== false)) return api;

      const total = ctx.all.length;
      const listed = ctx.all.filter((c) => c.has_website).length;
      const ranks = ctx.all.filter((c) => (c.web || {}).has_own_site).length;
      const paid = ctx.all.filter((c) => ((c.web || {}).owned || 0) > 0).length - ranks;

      if (listed === ranks) {
        // Not a degenerate chart — a win state, and it deserves its own sentence.
        wrap.append(h("div.mk-hero",
          h("span.disp.disp--md", { text: String(listed) }),
          h("span.unit", { text: `/${total} clinics` })));
        wrap.append(h("p.metric__c", { text: "Every clinic with a website ranks with it." }));
        return api;
      }

      wrap.append(h("div.mk-pair",
        h("div.mk-pair__c",
          h("span.disp.disp--sm", { text: String(listed) }),
          h("span.mk-pair__k.is-absent", { text: "list a website on Maps" })),
        h("div.mk-pair__c",
          h("span.disp.disp--sm", { text: String(ranks) }),
          h("span.mk-pair__k.is-owned", { text: "actually rank with one" }))));
      wrap.append(inst.dumbbell(listed, ranks, { max: total, class: "dumb--mirage" }));
      wrap.append(h("p.metric__c", {
        text: paid > 0
          ? `${paid} more reach the page only by paying — which still counts as ground they own, `
            + "because they choose where the click lands."
          : "The rest never reach a Google result page with a site of their own.",
      }));
      return api;
    },
  });

  /* ═══ MK-05 · Organic is leaking ══════════════════════════════════════════════
     Names its denominator out loud: organic is 673 of the 1,122 blocks, and
     conflating the two is the easiest honesty failure on this page. The 50%
     notch is scale furniture on the track, not a quota — target lines are
     banned and this instrument cannot draw one. */
  app.register({
    id: "mk05-organic", page: "market", size: "stat", title: "Organic is leaking",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const own = serpOwn(ctx.D);
      const o = ((own || {}).local_share || {}).organic || { local: 0, other: 0 };
      const n = o.local + o.other;
      const api = { wrap, panel: slots.panel };
      if (!setShown(api, n > 0)) return api;

      wrap.append(h("div.mk-hero",
        h("span.disp.disp--md", { text: `${Math.round((o.local / n) * 100)}%` }),
        h("span.unit", { text: "held locally" })));
      wrap.append(inst.shareMeter(o.local / n, {
        notch: 0.5, class: "smeter--tall",
        leftTitle: `${o.local} local`, rightTitle: `${o.other} not local`,
      }));
      wrap.append(h("p.metric__c", {
        text: `${o.local} of ${n} organic results on the ${own.totals.queries} pages we read `
              + "belong to a Guntur clinic.",
      }));
      return api;
    },
  });

  /* ═══ MK-06 · Ads nobody runs ═════════════════════════════════════════════════
     The lit part of the filament is the EMPTINESS. `sponsored` counts ad
     appearances on the captured pages — we cannot see spend, so nothing here
     says "bought", and the chain claim the inventory drafted is dropped rather
     than authored beside computed numbers. */
  app.register({
    id: "mk06-ads-none", page: "market", size: "stat", title: "Ads nobody runs",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const own = serpOwn(ctx.D);
      const api = { wrap, panel: slots.panel };
      if (!setShown(api, !!(own && own.totals.blocks))) return api;

      const total = ctx.all.length;
      const never = ctx.all.filter((c) => !(c.sponsored > 0)).length;
      const bt = own.totals.by_type;
      const adBlocks = (bt.sponsored_top || 0) + (bt.sponsored_mid || 0);
      const top = own.domains
        .map((d) => ({ d, ads: (d.by_type.sponsored_top || 0) + (d.by_type.sponsored_mid || 0) }))
        .sort((a, b) => b.ads - a.ads)[0];

      wrap.append(h("div.mk-hero",
        h("span.disp.disp--md", { text: String(never) }),
        h("span.unit", { text: `/${total} clinics` })));
      wrap.append(h("div.mk-filhost",
        inst.filament(never / (total || 1), { color: "var(--data-absent)" })));
      wrap.append(h("p.metric__c", {
        text: `never appeared as an ad on any of the ${own.totals.queries} result pages we read.`,
      }));
      if (never < total && top && top.ads > 0) {
        wrap.append(h("div.mk-filhost.mk-filhost--micro",
          inst.filament(top.ads / (adBlocks || 1), { color: "var(--data-borrowed)" })));
        wrap.append(h("p.caveat", {
          text: `One advertiser holds ${top.ads} of the market's ${adBlocks} sponsored blocks.`,
        }));
      }
      return api;
    },
  });

  /* ═══ MK-07 · The review economy ══════════════════════════════════════════════
     One dot per clinic on a √-scaled axis, edge-cropped so the 2,085 outlier runs
     off the card — which is the honest read of an outlier. The median is a
     GLOWING POINT, never a line, and it lands at 0.27 of the track: that
     position IS the picture. */
  app.register({
    id: "mk07-reviews", page: "market", size: "stat", dense: true,
    title: "The review economy",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap, panel: slots.panel, hot: null };
      drawEconomy(api, ctx);
      wrap.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "mk07-reviews");
      });
      wrap.addEventListener("pointerleave", () => bus.hover(null, "mk07-reviews"));
      return api;
    },
    // Static aggregate; only the subject's dot moves.
    update(api, ctx) { if (subjectChanged(api, ctx)) drawEconomy(api, ctx); },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  const STRIP_W = 340;

  function drawEconomy(api, ctx) {
    if (!setShown(api, ctx.D.reviews_available !== false)) return;
    const k = ctx.D.kpis || {};
    const rev = ctx.all.map((c) => c.reviews || 0);
    const maxR = Math.max(...rev, 1);
    // The payload's canonical median (154). Never recomputed — the true median
    // is 154.5 and two surfaces quoting two "typical" clinics is a bug.
    const med = k.median_reviews || 0;
    const mean = k.avg_reviews || 0;
    const pos = (r) => Math.sqrt(Math.max(r, 0)) / Math.sqrt(maxR);
    const subject = ctx.subject;

    api.wrap.textContent = "";
    api.wrap.append(h("div.mk-hero",
      h("span.disp.disp--md", { text: num(med) }),
      h("span.unit", { text: "median reviews" })));
    api.wrap.append(h("p.metric__c", {
      text: `mean ${num(mean)} · range ${num(Math.min(...rev))}–${num(maxR)}`,
    }));

    const items = ctx.all.map((c) => ({
      key: c.key, pos: pos(c.reviews || 0),
      you: !!(subject && c.key === subject.key),
      title: `${c.display_name} · ${num(c.reviews)} reviews`,
    }));
    const strip = h("div.mk-strip",
      inst.pointStrip(items, { width: STRIP_W, height: 44, r: 3.2, lanes: 3, spread: 8 }),
      h("i.ruler__dot.mk-strip__med", {
        style: { left: `${(pos(med) * STRIP_W).toFixed(1)}px` },
        title: `median ${num(med)}`,
      }));
    // The crop's PARENT is what the verifier reads for overflow, so the wrapper
    // is the compliance rather than a convenience.
    api.wrap.append(h("div.crop.mk-crop",
      h("div.edge-crop", { "aria-hidden": "true" }, strip)));
  }

  /* ═══ MK-08 · The four bands ══════════════════════════════════════════════════
     `bands.bands` has shipped since v2 and was read nowhere — v3 used only its
     `gaps`. Rows stay in payload order so the worst band reads first: the shape
     of this market is a wide bottom, and reversing it to flatter would be a lie.

     Counts are 1–2 digits at row scale, which is far below the measured Doto
     floor, so they ride Geist Mono. The distinction is size, not semantics. */
  app.register({
    id: "mk08-bands", page: "market", size: "stat", title: "The four bands",

    mount(body, ctx) {
      const wrap = h("div.stack.mk-bands.grow");
      body.append(wrap);
      const api = { wrap };
      drawBands(api, ctx);
      return api;
    },
    update(api, ctx) { if (subjectChanged(api, ctx)) drawBands(api, ctx); },
  });

  function drawBands(api, ctx) {
    const rows = ((ctx.D.bands || {}).bands) || [];
    const mine = ctx.subject ? store.bandOf(ctx.subject.visibility) : null;
    api.wrap.textContent = "";
    if (!rows.length) {
      api.wrap.append(h("p.panel__note", { text: "Bands not computed." }));
      return;
    }
    for (const b of rows) {
      api.wrap.append(h("div.mk-band" + (b.key === mine ? ".is-you" : ""), {
        "aria-label": `${b.label}: ${b.count} clinics, visibility ${b.lo} to ${b.hi}`,
      },
        h("span.mk-band__k", { text: b.label }),
        h("span.mk-band__r", bandRun(b.key, b.count)),
        h("span.mk-num", { text: String(b.count) })));
    }
  }

  /** A fixed-pitch run of band-coloured dots. An empty band renders as one
   *  hollow ring, never as a blank row — "nobody is Strong" is information. */
  function bandRun(key, n) {
    const cell = 8, r = 2.6, count = Math.max(n, 1);
    const dots = [];
    for (let i = 0; i < count; i++) {
      dots.push(s("circle", {
        cx: (i * cell + cell / 2).toFixed(1), cy: cell / 2, r,
        class: n ? `bandot bandot--${key}` : "bandot bandot--none",
      }));
    }
    return s("svg", { class: "viz mk-bandrun", viewBox: `0 0 ${count * cell} ${cell}`,
                      width: count * cell, height: cell,
                      preserveAspectRatio: "xMinYMid meet", "aria-hidden": "true" }, dots);
  }

  /* ═══ MK-09 · The opportunity map ═════════════════════════════════════════════
     The flagship cross-filter surface: hover -> bus, click -> select, and a
     rectangle BRUSH that filters every panel on the page.

     Zones are cut on the two axes actually plotted (demand × visibility). The
     tested analytics.quadrant_frame cuts on rating instead, and rating is a
     known trap here — 28 of 34 clinics sit between 4.8 and 5.0 — so using it
     would draw zone plates that contradict the picture. */
  app.register({
    id: "mk09-opportunity", page: "market", size: "square",
    title: "The opportunity map", sub: "demand against visibility",

    mount(body, ctx) {
      const host = h("div.chart.mk-chart");
      const legend = h("div.legend");
      const note = h("p.caveat", { text: "Drag a box to filter this page. Bubble size is review count." });
      body.append(host, legend, note);

      const api = { host, legend, chart: null, rows: [], off: new Set() };
      api.chart = charts.make(host, mapOption(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          if (p.seriesIndex !== 1) return;
          const r = api.rows[p.dataIndex];
          if (r) bus.hover(r.key, "mk09-opportunity");
        });
        api.chart.on("mouseout", () => bus.hover(null, "mk09-opportunity"));
        api.chart.on("click", (p) => {
          if (p.seriesIndex !== 1) return;
          const r = api.rows[p.dataIndex];
          if (r && store.select(r.key)) bus.emit("select", { key: r.key });
        });
        // The brush is the gesture that proves the dashboard is linked.
        api.chart.on("brushSelected", (e) => {
          const idx = (e.batch && e.batch[0] && e.batch[0].selected || [])
            .flatMap((sel) => sel.dataIndex || []);
          if (!idx.length) { store.setKeys(null); bus.emit("filter", {}); return; }
          store.setKeys(new Set(idx.map((i) => api.rows[i] && api.rows[i].key).filter(Boolean)));
          bus.emit("filter", {});
        });
      }
      buildZoneLegend(api, ctx);
      armBrush(api);
      return api;
    },

    update(api, ctx) {
      if (!api.chart) return;
      api.chart.setOption(mapOption(api, ctx), { replaceMerge: ["series", "graphic"] });
      armBrush(api);   // setOption resets the global cursor
    },
    highlight(api, key) {
      charts.emphasise(api.chart, api.rows.findIndex((r) => r.key === key), 1);
    },
  });

  /**
   * Put the chart into rect-brush mode.
   *
   * Declaring `brush: {...}` is NOT enough: ECharts only enters brush mode after
   * a toolbox button press or an explicit takeGlobalCursor. There is no toolbox
   * on this page (the design laws ban ECharts' own chrome), so without this the
   * `brushSelected` handler is unreachable and the panel's own caption promises a
   * gesture that does nothing. setOption resets the cursor, so re-arm after every
   * update.
   */
  function armBrush(api) {
    if (!api.chart) return;
    api.chart.dispatchAction({
      type: "takeGlobalCursor", key: "brush",
      brushOption: { brushType: "rect", brushMode: "single" },
    });
  }

  const ZONES = [
    { key: "stars", label: "Stars", why: "high demand, already visible" },
    { key: "hidden", label: "Hidden gems", why: "visible, but little demand" },
    { key: "vulnerable", label: "Vulnerable", why: "high demand, low visibility" },
    { key: "offradar", label: "Off radar", why: "low demand, low visibility" },
  ];

  function zoneOf(c, medDemand, medVis) {
    const hiD = (c.appearances || 0) >= medDemand, hiV = (c.visibility || 0) >= medVis;
    return hiD && hiV ? "stars" : (!hiD && hiV ? "hidden" : (hiD ? "vulnerable" : "offradar"));
  }

  function buildZoneLegend(api, ctx) {
    api.legend.textContent = "";
    for (const z of ZONES) {
      api.legend.append(h("button", {
        type: "button", "aria-pressed": String(!api.off.has(z.key)), title: z.why,
        onclick: () => {
          if (api.off.has(z.key)) api.off.delete(z.key); else api.off.add(z.key);
          buildZoneLegend(api, app.context());
          if (api.chart) api.chart.setOption(mapOption(api, app.context()),
                                             { replaceMerge: ["series"] });
        },
      }, h("i", { style: { background: `var(--zone-${z.key})` } }), z.label));
    }
  }

  function mapOption(api, ctx) {
    const all = ctx.all;
    const medDemand = median(all.map((c) => c.appearances || 0));
    const medVis = median(all.map((c) => c.visibility || 0));
    const rows = all.map((c) => ({
      key: c.key, name: c.display_name, zone: zoneOf(c, medDemand, medVis),
      x: c.appearances || 0, y: c.visibility || 0, r: c.reviews || 0,
      inView: ctx.keys.has(c.key),
      isSubject: ctx.subject && c.key === ctx.subject.key,
    }));
    api.rows = rows;

    const maxX = Math.max(...rows.map((r) => r.x), 1);
    // Faint tinted plates, drawn as data-space markAreas rather than floating text.
    const plates = [
      [[medDemand, medVis], [maxX * 1.08, 100], "stars"],
      [[0, medVis], [medDemand, 100], "hidden"],
      [[medDemand, 0], [maxX * 1.08, medVis], "vulnerable"],
      [[0, 0], [medDemand, medVis], "offradar"],
    ];

    return {
      grid: { left: 52, right: 26, top: 18, bottom: 44 },
      xAxis: charts.axis({ type: "value", name: "patient searches you show in",
                           nameLocation: "middle", nameGap: 26, max: maxX * 1.08 }),
      yAxis: charts.axis({ type: "value", name: "online visibility", nameLocation: "middle",
                           nameGap: 34, max: 100,
                           splitLine: { show: true, lineStyle: { color: P.data.gridline } } }),
      tooltip: charts.tooltip((p) => {
        const r = rows[p.dataIndex];
        if (!r) return "";
        return charts.tip(r.name, [["Visibility", r.y], ["Searches", r.x],
                                   ["Reviews", num(r.r)],
                                   ["Zone", (ZONES.find((z) => z.key === r.zone) || {}).label]]);
      }),
      dataZoom: [{ type: "inside", xAxisIndex: 0, filterMode: "none" }],
      brush: { toolbox: [], brushType: "rect", xAxisIndex: 0, yAxisIndex: 0, seriesIndex: 1,
               throttleType: "debounce", throttleDelay: 140,
               brushStyle: { borderWidth: 1, borderColor: P.ink[3],
                             color: P.data.track } },
      series: [{
        // Zone plates live on their own silent series. On the same series as the
        // bubbles, the markArea paints over them and the chart looks empty.
        type: "scatter", data: [], silent: true, z: 0,
        markArea: {
          silent: true,
          itemStyle: { opacity: 1 },
          data: plates.map(([a, b, zone]) => ([
            { xAxis: a[0], yAxis: a[1], itemStyle: { color: P.zone[zone] },
              label: { show: true, position: "insideTopLeft", color: P.ink[4], fontSize: 9,
                       formatter: (ZONES.find((z) => z.key === zone) || {}).label } },
            { xAxis: b[0], yAxis: b[1] },
          ])),
        },
      }, {
        // Per-datum itemStyle, not callbacks: ECharts honours a function for
        // itemStyle.color but silently drops opacity/borderWidth callbacks, and
        // the whole series renders invisible.
        type: "scatter", z: 5,
        data: rows.map((r) => ({
          value: [r.x, r.y],
          symbolSize: clamp(Math.sqrt(r.r) * 1.15, 8, 26),
          itemStyle: {
            color: r.isSubject ? P.data.you
                               : P.data[r.y >= medVis ? "owned" : "borrowed"],
            opacity: api.off.has(r.zone) ? 0.06 : (r.inView ? 0.82 : 0.1),
            // Not lime: the page's two limes are spent on MK-03 and MK-01a.
            borderColor: r.isSubject ? P.ink[1] : "transparent",
            borderWidth: r.isSubject ? 3 : 0,
          },
        })),
      }],
    };
  }

  /* ═══ MK-10 · The visibility league ═══════════════════════════════════════════
     Hairline tracks with a terminal dot, not chunky bars, and the two EMPIRICAL
     distribution gaps drawn as labelled voids — the insight a plain sorted bar
     chart destroys.

     The one card on the page that is NOT a filter consumer. That is a deliberate
     v3 call, kept, and it is captioned so it cannot read as a broken link. */
  const LEAGUE_SORTS = [
    { label: "Visibility", value: "visibility" },
    { label: "Reviews", value: "reviews" },
    { label: "Demand", value: "appearances" },
  ];

  app.register({
    id: "mk10-league", page: "market", size: "square", tools: true,
    title: "The visibility league", sub: "all 34, always",

    mount(body, ctx, slots) {
      const host = h("div.chart.mk-chart");
      const note = h("p.caveat", {
        text: "Every clinic, every time — the league deliberately ignores the page's filters "
              + "so the whole distribution stays readable. Click a row to select it.",
      });
      body.append(host, note);

      const api = { host, chart: null, sort: "visibility", rows: [] };
      // A segmented control, never a native <select> — the verifier counts those.
      if (slots.tools) {
        const paint = () => {
          slots.tools.textContent = "";
          slots.tools.append(inst.stepper(LEAGUE_SORTS, api.sort, (v) => {
            api.sort = v;
            paint();
            renderLeague(api, app.context());
          }, { class: "mk-seg", label: "Sort the league" }));
        };
        paint();
      }
      api.chart = charts.make(host, leagueOption(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          const r = api.rows[p.dataIndex];
          if (r) bus.hover(r.key, "mk10-league");
        });
        api.chart.on("mouseout", () => bus.hover(null, "mk10-league"));
        api.chart.on("click", (p) => {
          const r = api.rows[p.dataIndex];
          if (r && store.select(r.key)) bus.emit("select", { key: r.key });
        });
      }
      return api;
    },
    // NOT a filter consumer, so the only thing that can move it is the subject's
    // terminal ring — and re-rendering 34 categories on every brush is the most
    // expensive no-op on the page.
    update(api, ctx) { if (subjectChanged(api, ctx)) renderLeague(api, ctx); },
    highlight(api, key) {
      charts.emphasise(api.chart, api.rows.findIndex((r) => r.key === key));
    },
  });

  function leagueOption(api, ctx) {
    const metric = api.sort;
    const rows = ctx.all.slice().sort((a, b) => (a[metric] || 0) - (b[metric] || 0))
      .map((c) => ({
        key: c.key, name: short(c.display_name, 22), value: c[metric] || 0,
        visibility: c.visibility, reviews: c.reviews, appearances: c.appearances,
        isSubject: ctx.subject && c.key === ctx.subject.key,
      }));
    api.rows = rows;
    const maxV = Math.max(...rows.map((r) => r.value), 1);
    const axisMax = metric === "visibility" ? 100 : maxV;
    // Empirical, never hard-coded — and visibility-specific, so a sort by
    // reviews drops them rather than drawing voids that mean nothing.
    const gaps = metric === "visibility" ? (((ctx.D.bands || {}).gaps) || []) : [];

    return {
      grid: { left: 128, right: 30, top: 6, bottom: 24 },
      xAxis: charts.axis({ type: "value", max: axisMax }),
      yAxis: charts.axis({
        type: "category", data: rows.map((r) => r.name),
        axisLabel: { color: P.ink[3], fontFamily: "Geist", fontSize: 9.5, margin: 10,
                     interval: 0 },
      }),
      tooltip: charts.tooltip((p) => {
        const r = rows[(p[0] || p).dataIndex];
        return r ? charts.tip(r.name, [["Visibility", r.visibility],
                                       ["Reviews", num(r.reviews)],
                                       ["Searches", r.appearances]]) : "";
      }, "axis"),
      series: [
        { type: "bar", barWidth: 1.5, silent: true, z: 1, barGap: "-100%",
          itemStyle: { color: P.data.track }, data: rows.map(() => axisMax) },
        { type: "bar", barWidth: 1.5, z: 2,
          data: rows.map((r) => ({
            value: r.value,
            itemStyle: { color: r.isSubject ? P.data.you : P.data.aggregator },
          })),
          markArea: gaps.length ? {
            silent: true,
            data: gaps.map((g) => ([
              { xAxis: g.lo, itemStyle: { color: P.zone.offradar },
                label: { show: true, position: "insideTop", rotate: 90, color: P.ink[4],
                         fontSize: 8, formatter: "the market splits" } },
              { xAxis: g.hi },
            ])),
          } : undefined,
        },
        { type: "scatter", z: 3,
          data: rows.map((r, i) => ({
            value: [r.value, i],
            symbolSize: r.isSubject ? 8 : 6.5,
            itemStyle: { color: r.isSubject ? P.data.you : P.data.owned,
                         borderColor: r.isSubject ? P.ink[1] : "transparent",
                         borderWidth: r.isSubject ? 2.5 : 0 },
          })) },
      ],
    };
  }

  function renderLeague(api, ctx) {
    if (api.chart) api.chart.setOption(leagueOption(api, ctx),
                                       { replaceMerge: ["series", "yAxis", "xAxis"] });
  }

  /* ═══ MK-11 · Who owns the results ════════════════════════════════════════════
     1,122 result blocks as a domain × block-type dot matrix, so it reads as an
     instrument rack rather than a heatmap. Twelve domains plus a rollup, and the
     per-type local-share ticks under the headers are where all five
     `local_share` types finally get read — four of them shipped unread in v3.

     Static: the matrix is about DOMAINS, not clinics, so it never follows the
     clinic filter. It is still a hover consumer, because a domain row that maps
     to one clinic lights when that clinic is hovered anywhere else. */
  app.register({
    id: "mk11-ownership", page: "market", size: "band",
    title: "Who owns the Guntur results", sub: "every result block we read, by domain",

    mount(body, ctx, slots) {
      const wrap = h("div.own");
      body.append(wrap);
      const api = { wrap, panel: slots.panel };
      const own = serpOwn(ctx.D);
      if (!setShown(api, !!(own && own.totals.blocks))) return api;
      drawOwnership(api, ctx, own);
      return api;
    },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  // = views.BLOCK_ORDER, and the order a patient's eye travels the page.
  const TYPES = [
    ["sponsored_top", "Ads (top)"], ["places", "Map pack"],
    ["sponsored_mid", "Ads (mid)"], ["organic", "Organic"], ["ai_overview", "AI answer"],
  ];
  const TOP_N = 12;

  function drawOwnership(api, ctx, own) {
    const top = own.domains.slice(0, TOP_N);
    const rest = own.domains.slice(TOP_N);
    // NOT "(other)". `domains[4].domain` IS "(other)" — a real 57-block bucket
    // that sits inside the top twelve — so the rollup needs a name of its own or
    // the card shows two identically-labelled rows meaning different things.
    const rollup = rest.length ? {
      domain: `+${rest.length} more domains`, domain_known: true, kind: "other",
      clinics: 0, rollup: true,
      blocks: rest.reduce((n, d) => n + d.blocks, 0),
      by_type: Object.fromEntries(TYPES.map(([t]) =>
        [t, rest.reduce((n, d) => n + (d.by_type[t] || 0), 0)])),
    } : null;
    const rows = rollup ? top.concat([rollup]) : top;
    const maxCell = Math.max(1, ...rows.flatMap((d) => TYPES.map(([tk]) => d.by_type[tk] || 0)));

    api.wrap.textContent = "";
    const grid = h("div.own__grid");
    grid.append(h("div.own__h"), ...TYPES.map(([, label]) =>
      h("div.own__h.own__h--num", { text: label })),
      h("div.own__h.own__h--num", { text: "Blocks" }));

    // The local-share ticks: what fraction of each block type belongs to a
    // Guntur clinic at all. ai_overview reads 0 of 39 — that emptiness is the
    // only place this dataset's AI answers are allowed to appear.
    const share = own.local_share || {};
    grid.append(h("div.own__tickk", { text: "held locally" }));
    for (const [tk] of TYPES) {
      const b = share[tk] || { local: 0, other: 0 };
      const n = b.local + b.other;
      grid.append(h("div.own__cell",
        h("span.own__tick", { title: `${b.local} of ${n} ${tk.replace(/_/g, " ")} blocks are local` },
          h("i", { style: { width: `${n ? (b.local / n) * 100 : 0}%` } }))));
    }
    grid.append(h("div.own__h.own__h--num", { text: `${num(own.totals.mapped)} local` }));

    for (const d of rows) {
      const label = d.rollup
        ? h("div.own__row.is-rollup",
            h("span.swatch", { style: { background: `var(--kind-${d.kind})` } }),
            h("span.own__dom", { text: d.domain }))
        : h("button.own__row", {
            type: "button", data: { clinic: d.clinic_key || null },
            title: d.domain_known ? d.domain
              : `${d.domain} — ${d.clinics} clinics whose domain we could not read`,
            onclick: () => openDomainDrawer(d),
          },
            h("span.swatch", { style: { background: `var(--kind-${d.kind})` } }),
            h("span.own__dom", { text: d.domain_known ? d.domain
                                                      : `${d.domain} · ${d.clinics} clinics` }));
      grid.append(label);
      for (const [tk] of TYPES) {
        grid.append(h("div.own__cell", cellDots(d.by_type[tk] || 0, maxCell)));
      }
      grid.append(h("div.own__n.mk-mono", { text: num(d.blocks) }));
    }
    api.wrap.append(grid);
    api.wrap.append(h("p.caveat", {
      text: `The ${top.length} largest domains of ${own.domains.length}, and everything else `
            + `rolled into one row. A row marked with a clinic count is a bucket of clinic sites `
            + `whose domain the extraction never captured.`,
    }));
  }

  function cellDots(n, max) {
    if (!n) return h("span.own__zero", { text: "·" });
    const cols = Math.min(n, 12), cell = 6;
    const dots = [];
    for (let i = 0; i < cols; i++) {
      dots.push(s("circle", { cx: i * cell + cell / 2, cy: 5, r: 2,
                              opacity: (0.35 + 0.6 * (n / max)).toFixed(2) }));
    }
    const wrap = s("svg", { class: "viz", viewBox: `0 0 ${cols * cell} 10`, height: 10,
                            width: cols * cell, "aria-hidden": "true" },
                   s("g", { fill: "currentColor" }, dots));
    return h("span.own__cellwrap", { title: `${n} blocks` }, wrap,
             n > 12 ? h("span.own__more", { text: `${n}` }) : null);
  }

  function openDomainDrawer(d) {
    app.openDrawer(d.domain, (b) => {
      b.append(h("div.row",
        h("span.swatch", { style: { background: `var(--kind-${d.kind})` } }),
        h("span.metric__c", { text: KIND_TEXT[d.kind] || d.kind })));
      b.append(h("div.inner",
        h("div.metric__c", { text: `${d.blocks} result blocks across ${d.queries} searches` }),
        h("div.metric__c", { text: d.best_position
          ? `best position #${d.best_position} · median #${d.median_position}`
          : "no ranked position captured" }),
        h("div.metric__c", { text: `${d.mapped_blocks} of those blocks map to a Guntur clinic` })));
      if (d.clinics > 1) {
        b.append(h("p.caveat", {
          text: `${d.clinics} different Guntur clinics appear on this domain, so it carries no single owner.`,
        }));
      } else if (d.clinic) {
        b.append(h("p.panel__note", { text: `Belongs to ${d.clinic}.` }));
      }
    });
  }

  const KIND_TEXT = {
    own_clinic: "a Guntur clinic's own site",
    aggregator: "a directory carrying clinics",
    social: "a social profile",
    borrowed: "a clinic carried on someone else's page",
    other: "out of market",
  };

  /* ═══ MK-12 · Own ground vs borrowed ground ═══════════════════════════════════
     A centre-spine butterfly across ALL 34 clinics. The honest part is the
     hollow dot: twenty clinics hold neither kind of ground, and rendering them
     as a column of empty rings on the spine — rather than omitting them — is the
     chart's whole argument. */
  app.register({
    id: "mk12-ground", page: "market", size: "square",
    title: "Own ground vs borrowed ground", sub: "own site left, directories right",

    mount(body, ctx, slots) {
      const host = h("div.chart.mk-chart");
      const note = h("p.caveat");
      body.append(host, note);
      const api = { host, note, chart: null, rows: [], panel: slots.panel };
      if (!setShown(api, ctx.D.web_available !== false)) return api;
      api.chart = charts.make(host, obOption(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          const r = api.rows[p.dataIndex];
          if (r) bus.hover(r.key, "mk12-ground");
        });
        api.chart.on("mouseout", () => bus.hover(null, "mk12-ground"));
        api.chart.on("click", (p) => {
          const r = api.rows[p.dataIndex];
          if (r && store.select(r.key)) bus.emit("select", { key: r.key });
        });
      }
      drawGroundNote(api, ctx);
      return api;
    },
    update(api, ctx) {
      if (!api.chart) return;
      api.chart.setOption(obOption(api, ctx), { replaceMerge: ["series", "yAxis"] });
    },
    highlight(api, key) {
      charts.emphasise(api.chart, api.rows.findIndex((r) => r.key === key));
    },
  });

  function drawGroundNote(api, ctx) {
    const hollow = ctx.all.filter((c) => !((c.web || {}).owned || 0)
                                      && !((c.web || {}).borrowed || 0)).length;
    api.note.textContent =
      `${hollow} of ${ctx.all.length} clinics hold no ground at all — neither a site of their own `
      + "on a result page, nor a directory listing carrying them.";
  }

  function obOption(api, ctx) {
    const rows = ctx.all.map((c) => ({
      key: c.key, name: short(c.display_name, 20),
      owned: (c.web || {}).owned || 0, borrowed: (c.web || {}).borrowed || 0,
      inView: ctx.keys.has(c.key),
      isSubject: ctx.subject && c.key === ctx.subject.key,
    })).sort((a, b) => (b.owned + b.borrowed) - (a.owned + a.borrowed));
    api.rows = rows;
    const span = Math.max(...rows.map((r) => Math.max(r.owned, r.borrowed)), 1) * 1.15;

    return {
      grid: { left: 118, right: 24, top: 22, bottom: 26 },
      xAxis: charts.axis({ type: "value", min: -Math.ceil(span), max: Math.ceil(span),
                           minInterval: 1, splitNumber: 4,
                           axisLabel: { color: P.ink[4], fontSize: 9,
                                        formatter: (v) => Math.abs(Math.round(v)) || "" } }),
      yAxis: charts.axis({ type: "category", data: rows.map((r) => r.name), inverse: true,
                           axisLabel: { color: P.ink[3], fontSize: 9.5, interval: 0, margin: 10 } }),
      tooltip: charts.tooltip((p) => {
        const r = rows[(p[0] || p).dataIndex];
        return r ? charts.tip(r.name, [["Own site", r.owned], ["Directories", r.borrowed]]) : "";
      }, "axis"),
      series: [
        { type: "bar", barWidth: 1.5, stack: "w", z: 2,
          data: rows.map((r) => ({ value: -r.owned,
            itemStyle: { color: P.data.owned, opacity: r.inView ? 1 : 0.12 } })) },
        { type: "bar", barWidth: 1.5, stack: "w", z: 2,
          data: rows.map((r) => ({ value: r.borrowed,
            itemStyle: { color: P.data.borrowed, opacity: r.inView ? 1 : 0.12 } })) },
        { type: "scatter", z: 3,
          data: rows.map((r, i) => ({ value: [-r.owned, i], symbolSize: r.owned ? 6 : 0,
            itemStyle: { color: P.data.owned, opacity: r.inView ? 1 : 0.12 } })) },
        { type: "scatter", z: 3,
          data: rows.map((r, i) => ({ value: [r.borrowed, i], symbolSize: r.borrowed ? 6 : 0,
            itemStyle: { color: P.data.borrowed, opacity: r.inView ? 1 : 0.12 } })) },
        // Nothing at all: one hollow dot on the spine rather than an absent row.
        { type: "scatter", z: 3,
          data: rows.map((r, i) => ({
            value: [0, i], symbolSize: (!r.owned && !r.borrowed) ? 7 : 0,
            itemStyle: { color: "transparent", borderColor: P.data.absent, borderWidth: 1.4,
                         opacity: r.inView ? 1 : 0.12 },
          })) },
        // The subject, marked in ink rather than lime — this page's two limes are
        // spent on MK-03 and MK-01a.
        { type: "scatter", z: 4, silent: true,
          data: rows.map((r, i) => ({
            value: [0, i], symbolSize: r.isSubject ? 13 : 0,
            itemStyle: { color: "transparent", borderColor: P.ink[1], borderWidth: 1.4 },
          })) },
      ],
    };
  }

  /* ═══ MK-13 · Who is paying for the page ══════════════════════════════════════
     A filament shelf across all 34 clinics with the empty rows kept, because the
     emptiness IS the chart: 27 clinics never appeared as an ad on any page we
     read.

     The card is both the ads-toggle SOURCE and a filter CONSUMER, which is a
     conflict: pressing the toggle would narrow the page to the seven buyers and
     delete this card's entire argument. So MK-13 always renders `ctx.all` and
     only DIMS — the 27 stay on the shelf whatever the filter says.

     `sponsored` counts ad APPEARANCES on captured pages. We cannot see spend, so
     the copy never says "bought". */
  app.register({
    id: "mk13-paying", page: "market", size: "square", tools: true,
    title: "Who is paying for the page", sub: "ad appearances on the 78 result pages read",

    mount(body, ctx, slots) {
      const wrap = h("div.shelf.grow");
      const note = h("p.caveat");
      body.append(wrap, note);
      const api = { wrap, note, tools: slots.tools, panel: slots.panel,
                    rowEls: new Map(), hot: null, youKey: null };
      if (!setShown(api, ctx.D.web_available !== false)) return api;

      buildShelf(api, ctx);
      syncAdsToggle(api, ctx);

      wrap.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "mk13-paying");
      });
      wrap.addEventListener("pointerleave", () => bus.hover(null, "mk13-paying"));
      wrap.addEventListener("click", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        if (n && store.select(n.dataset.clinic)) bus.emit("select", { key: n.dataset.clinic });
      });
      return api;
    },

    update(api, ctx) {
      if (!api.rowEls.size) return;
      // One pass over a node list cached at mount. Never 34 rebuilt rows.
      inst.applyFilterClass(api.wrap, ctx.keys);
      const key = ctx.subject ? ctx.subject.key : null;
      if (api.youKey !== key) {
        const was = api.youKey && api.rowEls.get(api.youKey);
        if (was) was.classList.remove("is-you");
        const now = key && api.rowEls.get(key);
        if (now) now.classList.add("is-you");
        api.youKey = key;
      }
      syncAdsToggle(api, ctx);
    },

    highlight(api, key) {
      if (api.hot === key) return;
      const was = api.hot && api.rowEls.get(api.hot);
      if (was) was.classList.remove("is-hot");
      const now = key && api.rowEls.get(key);
      if (now) now.classList.add("is-hot");
      api.hot = key || null;
    },
  });

  function buildShelf(api, ctx) {
    const rows = ctx.all.slice().sort((a, b) => (b.sponsored || 0) - (a.sponsored || 0));
    const maxAd = Math.max(...rows.map((c) => c.sponsored || 0), 1);
    const buyers = rows.filter((c) => (c.sponsored || 0) > 0).length;
    const pages = serpQueries(ctx.D);

    api.wrap.textContent = "";
    api.rowEls.clear();
    for (const c of rows) {
      const n = c.sponsored || 0;
      const row = h("div.shelf__row" + (n ? "" : ".is-empty"), {
        data: { clinic: c.key },
        title: `${c.display_name} · ${n} of ${pages} result pages`,
      },
        h("span.shelf__name", { text: short(c.display_name, 24) }),
        h("span.shelf__fil", h("i", { style: { width: `${(n / maxAd) * 100}%` } })),
        h("span.shelf__n.mk-mono", { text: n ? String(n) : "" }));
      api.wrap.append(row);
      api.rowEls.set(c.key, row);
    }
    api.note.textContent = buyers
      ? `${rows.length - buyers} of ${rows.length} clinics never appeared as an ad on any of the `
        + `${pages} result pages read.`
      : "No clinic in Guntur has ever appeared as an ad on the result pages we read.";
    api.buyers = buyers;
  }

  /** The rail's one surviving facet, relocated into this card's header. */
  function syncAdsToggle(api, ctx) {
    if (!api.tools) return;
    const on = store.state.filter.ads;
    if (!api.adsBtn) {
      api.adsBtn = inst.togglePill({
        label: "Advertisers only", count: api.buyers,
        pressed: on,
        title: "Narrow the page to the clinics that have appeared as an ad",
        onclick: () => { store.setAds(!store.state.filter.ads); bus.emit("filter", {}); },
      });
      api.tools.append(api.adsBtn);
    }
    api.adsBtn.setAttribute("aria-pressed", String(on));
  }

  /* ═══ MK-14 · How far the market gets ═════════════════════════════════════════
     Five tick-ruler steps, not a trapezoid. The two steps that cut nothing are
     the finding, not a rendering fault: "+ Rating > 4" removes zero clinics,
     which is quiet live proof that the rating trap is real. */
  app.register({
    id: "mk14-funnel", page: "market", size: "half",
    title: "How far the market gets", sub: "clinics surviving each step",

    mount(body, ctx) {
      const wrap = h("div.stack.funnel.grow");
      body.append(wrap);
      const steps = ctx.D.funnel || [];
      if (!steps.length) {
        wrap.append(h("p.panel__note", { text: "The presence funnel has not been computed." }));
        return { wrap };
      }
      const top = steps[0].count || 1;
      for (const st of steps) {
        wrap.append(h("div.funnel__row",
          h("span.funnel__k", { text: st.step }),
          h("span.funnel__bar", inst.tickRuler(24, null, { height: 16 }),
            h("i", { style: { width: `${(st.count / top) * 100}%` } })),
          h("span.disp.disp--xs.funnel__n", { text: String(st.count) })));
      }
      wrap.append(h("p.caveat", {
        text: "Steps are cumulative, and their labels come from the pipeline rather than from "
              + "this page. Two of them cut nobody, which is itself the reading.",
      }));
      return { wrap };
    },
  });

  /* ═══ MK-15 · Demand & depth ══════════════════════════════════════════════════
     What patients search for, and how deep the results go. The merged card: v3's
     category counts plus the market's median position per category, which was in
     the payload but read only by the clinic page's polar.

     The depth ruler is scaled 7–11 with both endpoints labelled. The six medians
     span 8.0–10.0; on any zero-based axis that is a 14% band and the column
     reads flat. A stated truncated axis beats an honest-looking flat one. */
  const DEPTH_LO = 7, DEPTH_HI = 11;

  app.register({
    id: "mk15-demand", page: "market", size: "half",
    title: "Demand & depth", sub: "what patients search for, and how deep the results go",

    mount(body, ctx) {
      const wrap = h("div.stack.cats.grow");
      const note = h("p.caveat");
      body.append(wrap, note);
      const api = { wrap, note };
      drawCats(api, ctx);
      return api;
    },
    // A filter SOURCE, not a consumer: the rows redraw only to show which of
    // them are pressed.
    update(api, ctx) {
      const sig = [...store.state.filter.category].sort().join("|");
      if (api._cats === sig) return;
      api._cats = sig;
      drawCats(api, ctx);
    },
  });

  function drawCats(api, ctx) {
    const cats = (ctx.D.categories || []).slice()
      .sort((a, b) => (b.count || 0) - (a.count || 0));
    const market = ctx.D.intents_market || {};
    const total = cats.reduce((a, c) => a + (c.count || 0), 0) || 1;
    const maxC = Math.max(...cats.map((c) => c.count || 0), 1);
    const active = store.state.filter.category;

    api.wrap.textContent = "";
    api.wrap.append(h("div.cats__head",
      h("span"), h("span", { text: "demand" }), h("span"),
      h("span.cats__scale", h("i", { text: `#${DEPTH_LO}` }), h("i", { text: `#${DEPTH_HI}` }))));

    for (const c of cats) {
      const on = active.has(c.category);
      const med = market[c.category];
      api.wrap.append(h("button.cats__row" + (on ? ".is-on" : ""), {
        type: "button", "aria-pressed": String(on),
        title: med === undefined
          ? `${c.category} — ${c.count} searches; no market position recorded`
          : `${c.category} — ${c.count} searches; the market's median position is #${med}`,
        onclick: () => { store.toggleFacet("category", c.category); bus.emit("filter", {}); },
      },
        h("span.cats__k", { text: c.category }),
        h("span.cats__bar", h("i", { style: { width: `${(c.count / maxC) * 100}%` } })),
        h("span.cats__n.mk-mono", { text: `${c.count}` }),
        med === undefined
          ? h("span.cats__d", h("span.cats__dash", { text: "—" }))
          : h("span.cats__d",
              h("i.cats__dtrack"),
              h("i.cats__ddot", {
                style: { left: `${clamp((med - DEPTH_LO) / (DEPTH_HI - DEPTH_LO), 0, 1) * 100}%` },
              }),
              h("span.disp.disp--xs.cats__dv", { text: med.toFixed(1) }))));
    }

    const top = cats[0];
    api.note.textContent = (top
      ? `${top.category} is ${top.count} of ${total} searches — `
        + `${Math.round((top.count / total) * 100)}% of everything patients ask. `
      : "")
      + "Depth is the market's median result position for that intent, on a 7-to-11 scale. "
      + "Choosing a row filters the page to clinics that appear in that intent at all.";
  }

  /* ═══ MK-16 · Every clinic ════════════════════════════════════════════════════
     A borderless table: no zebra stripes, no vertical rules, no grid. The
     visibility track is NEUTRAL ink — the band-chroma census on this page is
     MK-01 and MK-08 and nothing else — and `web_score` is a two-state mark
     rather than a numeral, because 28 of the 34 scores sit at exactly 0 or 100
     and a numeral column would fake granularity across the six in between. */
  const COLS = [
    { key: "display_name", label: "Clinic", type: "text" },
    { key: "visibility", label: "Visibility", type: "track" },
    { key: "visibility_rank", label: "Rank", type: "num" },
    { key: "maps_score", label: "Maps gap", type: "num" },
    { key: "web_score", label: "Web ground", type: "mark" },
    { key: "pos_avg", label: "Avg pos", type: "dec" },
    { key: "reviews", label: "Reviews", type: "num" },
    { key: "appearances", label: "Searches", type: "num" },
    { key: "sponsored", label: "Ads", type: "num" },
  ];

  app.register({
    id: "mk16-table", page: "market", size: "band",
    title: "Every clinic", sub: "click a row to open its report",

    mount(body, ctx) {
      const wrap = h("div.tbl-wrap.mk-tblwrap");
      body.append(wrap);
      const api = { wrap, sort: "visibility", dir: -1 };
      drawTable(api, ctx);
      return api;
    },
    update(api, ctx) { drawTable(api, ctx); },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  function drawTable(api, ctx) {
    const rows = ctx.filtered.slice().sort((a, b) => {
      const va = a[api.sort], vb = b[api.sort];
      if (typeof va === "string") return api.dir * va.localeCompare(vb);
      return api.dir * ((va || 0) - (vb || 0));
    });

    const table = h("table.tbl");
    const thead = h("thead");
    const tr = h("tr");
    for (const col of COLS) {
      tr.append(h("th" + (col.type === "text" ? "" : ".is-num"),
        h("button", {
          type: "button",
          "aria-sort": api.sort === col.key ? (api.dir === -1 ? "descending" : "ascending") : "none",
          text: col.label,
          onclick: () => {
            if (api.sort === col.key) api.dir *= -1;
            else { api.sort = col.key; api.dir = col.type === "text" ? 1 : -1; }
            drawTable(api, app.context());
          },
        })));
    }
    thead.append(tr);
    table.append(thead);

    const tbody = h("tbody");
    if (!rows.length) {
      // v3 rendered an empty tbody here. A brush and a pill compose to zero
      // clinics, and the table is one of the two places a user notices it.
      tbody.append(h("tr.tbl__none", h("td", { colspan: String(COLS.length) },
        h("span", { text: "No clinic matches these filters. " }),
        h("button.tbl__clear", {
          type: "button", text: "Clear them",
          onclick: () => { store.clearFilters(); bus.emit("filter", {}); },
        }))));
    }
    for (const c of rows) {
      const isYou = ctx.subject && c.key === ctx.subject.key;
      const row = h("tr" + (isYou ? ".is-you" : ""), {
        data: { clinic: c.key },
        onclick: () => {
          // select() returns false for an UNCHANGED key, so navigation must not
          // be gated on it — v3 made clicking the current subject's row a no-op.
          if (store.select(c.key)) bus.emit("select", { key: c.key });
          app.go("clinic");
        },
        onpointerenter: () => bus.hover(c.key, "mk16-table"),
        onpointerleave: () => bus.hover(null, "mk16-table"),
      });
      for (const col of COLS) {
        const v = c[col.key];
        if (col.type === "text") {
          row.append(h("td.tbl__name", { text: short(v, 34), title: c.name }));
        } else if (col.type === "track") {
          row.append(h("td.is-num",
            h("span.tbl__track", h("i", { style: { width: `${clamp(v || 0, 0, 100)}%` } })),
            h("span.tbl__v", { text: String(v) })));
        } else if (col.type === "mark") {
          // Presence, never the score: web_score > 0 lights 26 clinics and would
          // put a mark beside two clinics the map calls "directories only".
          const own = store.presenceOf(c) === "own";
          row.append(h("td.is-num", inst.twoState(own, {
            onTitle: `own ground on the open web · web score ${num(v)}`,
            offTitle: `no ground of their own · web score ${num(v)}`,
            onLabel: "holds own ground", offLabel: "no ground of their own",
          })));
        } else if (col.type === "dec") {
          row.append(h("td.is-num", { text: v === null || v === undefined ? "—" : Number(v).toFixed(1) }));
        } else {
          row.append(h("td.is-num", { text: v === null || v === undefined ? "—" : num(v) }));
        }
      }
      tbody.append(row);
    }
    table.append(tbody);
    api.wrap.textContent = "";
    api.wrap.append(table);
  }
})(window.DI);
