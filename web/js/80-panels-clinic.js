/* ── "Your Clinic" — the nineteen v4 cards ─────────────────────────────────────
   Contract: docs/redesign/v4/V0_CARD_INVENTORY.md §3. Registration order IS DOM
   order IS reading order, so the bento comes out as the inventory states it:

     A  01 visibility · 02 rank · 03 what's possible          (wide · wide · wide)
     B  04 blend · 05 position · 06 ready-to-book · 07 demand (stat ×4)
     C  08 examination · 09 score anatomy                     (half ×2)
     D  10 the page · 11 who's there · 12 intent polar        (panel · tall · tall)
     E  13 web ground · 14 reviews · 15 ads · 16 where        (stat ×4)
     F  17 patient voice · 18 praised/flagged                 (half ×2)
     G  19 the prescription                                   (band)

   Two rules this file is built around, both new in v4:

   1. **Your Clinic is a static-read page.** Nothing here emits `select`, touches
      a facet, or emits `filter` — v3's three cross-filter wirings (the twin
      jewels, the polar's category toggle, the constellation) are deleted, not
      ported. `bus` is deliberately not even imported, so the guarantee is
      structural rather than a convention. The cross-filter buses live on The
      Market, which is the page they actually filter.
   2. **Mount once.** mount() builds the DOM and returns a handle; update()
      patches through that handle. Nothing is ever re-mounted or re-parented. */
(function (DI) {
  "use strict";

  const { h, s, inst, store, app, num, pct, clamp, short } = DI;

  /* The three denominators, kept straight (inventory §6): 50 Maps queries · 78
     captured result pages · 80 searches total. Only the 78 rides in the payload
     (serp.ownership.totals.queries); the Maps figure is the count of distinct OK
     queries behind `appearances` and has no payload field, so it is named here
     once rather than inlined into copy five times. */
  const MAPS_QUERIES = 50;
  const serpQueries = (D) => (((D.serp || {}).ownership || {}).totals || {}).queries || 78;

  /* views._CENTER — the Guntur city core the km rings are measured from. */
  const CORE = [16.3067, 80.4365];

  const bandLabel = (b) => ({ alarm: "Nearly invisible", caution: "Below market",
                              steady: "Partway there", clear: "Strong" }[b] || "");

  /* Zero plan steps is a state TWO cards share — YC-03's span would degenerate
     to `#1 → #1` and YC-19 has nothing to stack — with identical copy. One
     guard, one string, two consumers. */
  const AT_CEILING = "Nothing to prescribe — already at the ceiling";
  const atCeiling = (c) => !!(c && c.plan && (c.plan.steps || []).length === 0);

  /** Hide a whole card. `[hidden]` is only display:none at UA level and .panel
   *  sets display:flex, which defeats it; 25-clinic.css carries the real rule. */
  function setShown(api, on) {
    if (api.panel) api.panel.hidden = !on;
    return on;
  }

  /* ═══ YC-01 · Visibility jewel ════════════════════════════════════════════════
     The hero. State-mapped: the recipe follows the score band, so a 13 renders in
     alarm and can never read as reassuring. The context dot-column that used to
     crowd the jewel's face moved into the ↗ drawer, where it is a comparison you
     ask for rather than one shouted at you. */
  app.register({
    id: "yc01-visibility", page: "clinic", size: "wide", subject: true,
    aria: "Online visibility",

    mount(body, ctx) {
      const host = h("div.yc-jewelhost");
      body.append(host);
      const api = { host };
      drawVisibility(api, ctx);
      return api;
    },
    update: drawVisibility,
    expand(api, ctx) { openVisibilityDrawer(ctx); },
  });

  function drawVisibility(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const band = store.bandOf(c.visibility);
    const total = c.visibility_total || ctx.all.length;
    api.host.textContent = "";
    api.host.append(inst.jewel({
      family: band, label: "Online visibility", value: c.visibility,
      sub: `${bandLabel(band)} · #${c.visibility_rank} of ${total} in Guntur`,
      ariaLabel: `Online visibility ${c.visibility} of 100. ${bandLabel(band)}. ` +
                 `Ranked ${c.visibility_rank} of ${total}.`,
    }));
  }

  function openVisibilityDrawer(ctx) {
    const c = ctx.subject;
    if (!c) return;
    const sorted = ctx.all.slice().sort((a, b) => (a.visibility || 0) - (b.visibility || 0));
    const idx = sorted.findIndex((x) => x.key === c.key);
    app.openDrawer("Online visibility", (b) => {
      b.append(h("p.panel__note", {
        text: `Every clinic we read in Guntur, weakest to strongest. Yours is the lit ` +
              `column: ${c.visibility} of 100, ranked #${c.visibility_rank} of ${sorted.length}.`,
      }));
      b.append(h("div.yc-drawviz",
        inst.dotColumn(sorted.map((x) => x.visibility || 0), { highlight: idx, height: 52 })));
      b.append(h("p.caveat", {
        text: "The score is 60% Google Maps and 40% Google web search, and higher is better. " +
              "The two halves behind it are on the 60/40 card.",
      }));
    });
  }

  /* ═══ YC-02 · Market rank jewel ═══════════════════════════════════════════════
     The index jewel NEVER state-maps: a rank is an index, not a condition. Its
     hero rides display-light rather than dot-white — the atlas's one sanctioned
     exception, and the reference's own "7-10" is the evidence for it. */
  app.register({
    id: "yc02-rank", page: "clinic", size: "wide", subject: true,
    aria: "Market rank",

    mount(body, ctx) {
      const host = h("div.yc-jewelhost");
      body.append(host);
      const api = { host };
      drawRank(api, ctx);
      return api;
    },
    update: drawRank,
  });

  function drawRank(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const total = c.visibility_total || ctx.all.length;
    const frac = (c.visibility_rank - 1) / Math.max(1, total - 1);
    api.host.textContent = "";
    api.host.append(inst.jewel({
      family: "index", register: "light", label: "Market rank",
      value: `#${c.visibility_rank}`, unit: `/${total}`,
      sub: "against every clinic in this report",
      viz: inst.pointRuler(total, frac, { height: 20 }),
      ariaLabel: `Ranked ${c.visibility_rank} of ${total} clinics in Guntur.`,
    }));
  }

  /* ═══ YC-03 · What's possible ═════════════════════════════════════════════════
     The dark teaser for the prescription band at the foot of the page. It leads
     with the TOP-TWO projection, not the full plan: the full plan lands 27 of 34
     clinics on exactly (100, #2), so it tells this clinic nothing, while the
     first-two-fixes rank genuinely varies across the market (1–11). */
  app.register({
    id: "yc03-possible", page: "clinic", size: "wide", rung: "dark", subject: true,
    title: "What's possible",

    mount(body, ctx) {
      const wrap = h("div.stack.yc-teaser");
      body.append(wrap);
      const api = { wrap };
      drawTeaser(api, ctx);
      return api;
    },
    update: drawTeaser,
  });

  function drawTeaser(api, ctx) {
    const c = ctx.subject;
    const plan = c && c.plan;
    api.wrap.textContent = "";
    if (!plan) return;
    if (atCeiling(c)) {
      api.wrap.append(h("p.panel__note", { text: AT_CEILING }));
      return;
    }
    const top2 = plan.compound.top2, all = plan.compound.all;
    api.wrap.append(
      inst.deltaSpan(`#${plan.now.rank}`, `#${top2.rank}`, { size: "sm" }),
      h("p.metric__c", {
        text: `Visibility ${plan.now.vis} → ${top2.vis} of 100. Closing every gap tops out ` +
              `at #${all.rank} of ${c.visibility_total} — the arithmetic ceiling in this ` +
              `market, not a forecast.`,
      }),
      h("div.row", inst.pill("on your first two fixes", "lime")));
  }

  /* ═══ YC-04 · The 60/40 blend ═════════════════════════════════════════════════
     Two labelled segments over one track, each half filling to its own score —
     so the eye reads WHICH side of the weighted blend is carrying the number.
     Deliberately not a gauge and not a spectrum: `web_score` is near-binary
     (28 of 34 sit at exactly 0 or 100) and a gauge would fake granularity.

     Both are GAP measures: higher means more ground to make up, the inverse of
     the visibility jewel beside them. The labels say "gap" for that reason, and
     the worst side is marked with a lime pill — never a lime segment fill. */
  app.register({
    id: "yc04-blend", page: "clinic", size: "stat", subject: true,
    title: "The 60/40 blend",

    mount(body, ctx) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap };
      drawBlend(api, ctx);
      return api;
    },
    update: drawBlend,
  });

  function drawBlend(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const webOn = ctx.D.web_available !== false;
    const maps = c.maps_score, web = c.web_score;
    const worst = (webOn && web !== null && maps !== null && web > maps) ? "web" : "maps";

    api.wrap.textContent = "";
    const grid = h("div.yc-pair");
    const cell = (key, value, label) => h("div.yc-pair__cell" + (key === worst ? ".is-worst" : ""),
      h("span.disp.disp--sm", { text: num(value) }),
      h("span.yc-pair__k", { text: label }),
      key === worst ? inst.pill("widest gap", "lime") : null);
    grid.append(cell("maps", maps, "Maps gap · 60%"));
    if (webOn) grid.append(cell("web", web, "Web gap · 40%"));
    api.wrap.append(grid);

    api.wrap.append(h("p.caveat", {
      text: webOn ? "Both run 0–100; higher means more ground to make up."
                  : "Maps only — web not yet read.",
    }));

    const segs = webOn
      ? [{ width: 0.6, fill: (maps || 0) / 100, tone: "is-maps" },
         { width: 0.4, fill: (web || 0) / 100, tone: "is-web" }]
      : [{ width: 1, fill: (maps || 0) / 100, tone: "is-maps" }];
    api.wrap.append(inst.edgeCrop(inst.segmentTrack(segs), { class: "yc-crop--track" }));
  }

  /* ═══ YC-05 · Average Maps position ═══════════════════════════════════════════ */
  app.register({
    id: "yc05-position", page: "clinic", size: "stat", subject: true,
    title: "Average Maps position",

    mount(body, ctx) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap };
      drawPosition(api, ctx);
      return api;
    },
    update: drawPosition,
  });

  function drawPosition(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const pos = c.pos_avg;
    api.wrap.textContent = "";
    // A position SPANS, so it takes the light register, never dot-matrix.
    api.wrap.append(h("div.yc-hero",
      h("span.disp.disp--md", { text: pos === null ? "—" : pos.toFixed(1) }),
      h("span.unit", { text: "on Google Maps" })));
    api.wrap.append(h("p.metric__c", {
      text: pos === null ? "not seen in the Maps pack"
        : (pos <= 3 ? "top of the pack" : pos <= 7 ? "mid-pack" : "buried below the fold"),
    }));
    if (pos !== null) {
      api.wrap.append(inst.edgeCrop(
        inst.pointRuler(30, clamp((pos - 1) / 14, 0, 1), { height: 22 })));
    }
  }

  /* ═══ YC-06 · Ready-to-book share ═════════════════════════════════════════════
     A ten-dot meter, not a bar and not a gauge — the eye counts it. Eleven of the
     34 clinics sit at exactly zero, so the all-dead read has to be legible rather
     than look like a card that failed to draw. */
  app.register({
    id: "yc06-intent-share", page: "clinic", size: "stat", subject: true,
    title: "Ready-to-book share",

    mount(body, ctx) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap };
      drawIntentShare(api, ctx);
      return api;
    },
    update: drawIntentShare,
  });

  function drawIntentShare(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const hi = c.high_intent;
    const lit = hi === null ? 0 : Math.round(hi * 10);
    api.wrap.textContent = "";
    api.wrap.append(h("div.yc-hero",
      h("span.disp.disp--md", { text: hi === null ? "—" : `${Math.round(hi * 100)}%` }),
      h("span.unit", { text: "of your demand" })));
    api.wrap.append(h("div.yc-meter", inst.dotMeter(10, lit)));
    api.wrap.append(h("p.metric__c", {
      text: hi === null ? "ready-to-book share not measured"
        : lit === 0 ? "no ready-to-book searches yet — pricing, appointment and near-me"
          : "is ready to book — pricing, appointment and near-me searches",
    }));
  }

  /* ═══ YC-07 · Demand census ═══════════════════════════════════════════════════
     Fifty cells, one per Maps search we ran, lit where the clinic surfaced. The
     denominator is drawn, not just stated: nine lit out of fifty says something
     the numeral nine cannot. */
  app.register({
    id: "yc07-demand", page: "clinic", size: "stat", dense: true, subject: true,
    title: "Demand census",

    mount(body, ctx) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap };
      drawDemand(api, ctx);
      return api;
    },
    update: drawDemand,
  });

  function drawDemand(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const n = c.appearances || 0;
    api.wrap.textContent = "";
    api.wrap.append(h("div.yc-hero",
      h("span.disp.disp--sm", { text: String(n) }),
      h("span.unit", { text: `/${MAPS_QUERIES} Maps searches` })));
    api.wrap.append(h("div.yc-census",
      inst.dotCensus(MAPS_QUERIES, { lit: n, per: 25, cell: 10, r: 3, scale: 1.25 })));
    api.wrap.append(h("p.caveat", {
      text: `Every cell is one of the ${MAPS_QUERIES} searches we ran on Google Maps.`,
    }));
  }

  /* ═══ YC-08 · The examination ═════════════════════════════════════════════════
     Five checks, FIVE DIFFERENT INSTRUMENTS. v2 rendered five identical grey
     rounded rectangles differentiated only by a status pill, which is why it read
     as a disabled form rather than a diagnostic.

     Status is carried by FILL and ALPHA. The only hue in the rack is a single
     caution accent, on the weakest row alone. */

  // Presentation-layer copy. modules/report.py stays byte-identical; the "maps"
  // check is RELABELLED here because it measures local-pack presence across the
  // 78 SERPs we read, not whether the clinic is on Google Maps — all 34 are.
  const CHECK_COPY = {
    website: { label: "Your own website", why: "somewhere for a patient to land" },
    search: { label: "Ranking in Google search", why: "found when they type a treatment" },
    maps: { label: "In the local pack", why: "the three-clinic map box, across the searches we read" },
    reviews: { label: "Google reviews", why: "the trust signal patients read first" },
    phone: { label: "A number to call", why: "the last step before they book" },
  };

  app.register({
    id: "yc08-examination", page: "clinic", size: "half", subject: true,
    title: "The examination", sub: "five checks, five instruments",

    mount(body, ctx) {
      const rack = h("div.rack.yc-rack");
      body.append(rack);
      const api = { rack };
      drawRack(api, ctx);
      return api;
    },
    update: drawRack,
    expand(api, ctx) { openExamDrawer(ctx); },
  });

  /** The single weakest check. The plan is already sorted by lift, so its first
   *  step names the row that costs the most; a clinic with no plan falls back to
   *  the first failing check in scorecard order. */
  function weakestCheck(c) {
    const steps = (c.plan && c.plan.steps) || [];
    for (const st of steps) {
      if (CHECK_COPY[st.key]) return st.key;
    }
    const bad = (c.scorecard || []).find((x) => x.status === "bad");
    return bad ? bad.key : null;
  }

  function drawRack(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const web = c.web || {};
    const D = ctx.D;
    const nQ = serpQueries(D);
    const medianReviews = (D.kpis || {}).median_reviews || 0;
    const meanReviews = (D.kpis || {}).avg_reviews || 0;
    const weak = weakestCheck(c);

    api.rack.textContent = "";
    for (const check of (c.scorecard || [])) {
      const copy = CHECK_COPY[check.key] || { label: check.label, why: "" };
      const value = valueFor(check, web, nQ, c, medianReviews);
      const note = noteFor(check, c, medianReviews, meanReviews);
      const row = h("div.irow" + (check.key === weak ? ".is-weakest" : ""), {
        // The accessible name must carry the SAME corrected copy the sighted row
        // shows, not report.py's raw string, or the two disagree.
        "aria-label": `${copy.label}: ${value}. ${note}`,
      });
      row.append(h("div.irow__k", { text: copy.label }));
      row.append(h("div.irow__i", instrumentFor(check, c, web, nQ, medianReviews, meanReviews)));
      row.append(valueCell(check, value, nQ, c, medianReviews));
      api.rack.append(row);
    }
  }

  /** Row values are caption-face text except two: the local-pack count and the
   *  review pair are COUNTS, so both take dot-ink at the small step with their
   *  denominators on the proportional face. */
  function valueCell(check, value, nQ, c, medianReviews) {
    const cell = h("div.irow__v");
    if (check.key === "maps") {
      cell.append(h("span.disp.disp--sm", { text: String((c.web || {}).in_places || 0) }),
                  h("span.irow__u", { text: `of ${nQ}` }));
    } else if (check.key === "reviews") {
      cell.append(h("span.disp.disp--sm", { text: String(c.reviews || 0) }),
                  h("span.irow__u", { text: "vs" }),
                  h("span.disp.disp--sm.is-quiet", { text: String(medianReviews) }),
                  h("span.irow__u", { text: "median" }));
    } else {
      cell.textContent = value;
    }
    return cell;
  }

  /** Panel-layer copy. modules/report.py stays byte-identical; these overrides
   *  exist only where its wording would contradict the instrument beside it or
   *  state something untrue of this clinic. */
  function noteFor(check, c, medianReviews, meanReviews) {
    if (check.key === "reviews") {
      // The instrument plots against the MEDIAN (the typical clinic) while the
      // score is computed against the MEAN. Saying only one of those produced a
      // row that showed the clinic ahead while its own note called it behind.
      const you = c.reviews || 0;
      const side = you >= medianReviews ? "ahead of" : "behind";
      return `${num(you)} reviews — ${side} the typical Guntur clinic at ${num(medianReviews)}. ` +
             `The score measures you against the market mean of ${num(meanReviews)}, which two ` +
             `large chains pull upward.`;
    }
    // report.py credits a PAID placement as "your own clinic website shows up in
    // Google", which is false for a clinic that has no website at all.
    if (check.key === "search" && !c.has_website && ((c.web || {}).owned || 0) > 0) {
      return "You appear through paid placement only — and there is no website of yours " +
             "for that click to land on.";
    }
    return check.note;
  }

  function valueFor(check, web, nQ, c, medianReviews) {
    if (check.key === "maps") return `${web.in_places || 0} of ${nQ}`;
    // The instrument plots against the MEDIAN, so the number beside it must too —
    // report.py's own string quotes the mean and would contradict the dumbbell.
    if (check.key === "reviews") return `${num(c.reviews)} vs ${num(medianReviews)} median`;
    if (check.key === "search") return web.has_own_site ? "your site ranks"
      : (web.owned > 0 ? "paid placement only"
        : (web.borrowed > 0 ? "directories only" : "not found"));
    return check.value;
  }

  /** One instrument per check — the point of the card. */
  function instrumentFor(check, c, web, nQ, medianReviews, meanReviews) {
    const good = check.status === "good";
    switch (check.key) {
      case "website":
      case "phone":
        // A filament: lit when present, a broken ghost when not. No status chip.
        return good
          ? inst.filament(1, { color: "var(--data-owned)" })
          : h("div.filament.filament--broken", { "aria-hidden": "true" });

      case "search":
        // A 78-dot census: lit where the clinic's own site ranks, half-lit where
        // a directory carries it, dead where it is absent. This is where the
        // 1122-block corpus finally shows up in the clinic view.
        return inst.dotCensus(nQ, { lit: web.owned || 0, half: web.borrowed || 0,
                                    per: 26, cell: 6, r: 1.9, scale: 1.2 });

      case "maps":
        // A tick field with a filled span 0 -> in_places/queries.
        return inst.spanRuler(clamp((web.in_places || 0) / Math.max(1, nQ), 0, 1),
                              { height: 16, ticks: 26 });

      case "reviews":
        // A dumbbell against the MEDIAN, with the skewed mean drawn as a ghost
        // tick so the honest comparator is the one that reads loudest.
        return inst.dumbbell(c.reviews || 0, medianReviews,
                             { ghost: meanReviews, scale: "sqrt" });

      default:
        return h("div");
    }
  }

  function openExamDrawer(ctx) {
    const c = ctx.subject;
    if (!c) return;
    const kpis = ctx.D.kpis || {};
    const med = kpis.median_reviews || 0, mean = kpis.avg_reviews || 0;
    app.openDrawer("The examination", (b) => {
      for (const check of (c.scorecard || [])) {
        const copy = CHECK_COPY[check.key] || { label: check.label, why: "" };
        const block = h("div.inner",
          h("div.yc-drawk", { text: copy.label },
            h("small", { text: copy.why })),
          // Same corrected copy as the row — three surfaces, one statement.
          h("p.panel__note", { text: noteFor(check, c, med, mean) }));
        const step = ((c.plan && c.plan.steps) || []).find((x) => x.key === check.key);
        if (step) {
          block.append(h("div.metric__c", { text: "Closing this one gap" }),
            inst.deltaSpan(`#${c.visibility_rank}`, `#${step.rank_after}`, { size: "xs" }),
            h("div.metric__c", {
              text: `visibility ${c.visibility} → ${step.vis_after} (+${step.lift})`,
            }));
        }
        b.append(block);
      }
      const above = (ctx.all || []).filter((x) => (x.reviews || 0) > mean).length;
      b.append(h("p.caveat", {
        text: `The dumbbell plots you against the median (${num(med)}); the faint tick is the ` +
              `mean (${num(mean)}). Only ${above} of ${(ctx.all || []).length} clinics sit above ` +
              `that mean, which is why the median is the fairer read of a typical clinic.`,
      }));
      b.append(h("p.caveat", {
        text: "The local-pack row measures the map box across the Google result pages we read — " +
              "not whether you are listed on Google Maps. Every clinic in this report is.",
      }));
    });
  }

  /* ═══ YC-09 · Score anatomy ═══════════════════════════════════════════════════
     Six earned/max hairline bars. `breakdown` has shipped in the payload since
     v2 and was rendered nowhere: until now the score was a number with no
     arithmetic behind it. The track IS the maximum, so no component can render
     as a zero-width nothing. */
  app.register({
    id: "yc09-anatomy", page: "clinic", size: "half", subject: true,
    title: "Score anatomy", sub: "where your 100 points went",

    mount(body, ctx) {
      const grid = h("div.yc-anat");
      body.append(grid);
      const api = { grid };
      drawAnatomy(api, ctx);
      return api;
    },
    update: drawAnatomy,
  });

  const ANAT_LABEL = {
    website: "Own website", search: "Ranks in search", maps: "In the local pack",
    reviews: "Reviews vs market", phone: "Phone listed", breadth: "Search breadth",
  };

  function drawAnatomy(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    api.grid.textContent = "";
    for (const row of (c.breakdown || [])) {
      api.grid.append(h("div.yc-anat__row", {
        "aria-label": `${ANAT_LABEL[row.key] || row.label}: ${row.earned} of ${row.max} points`,
      },
        h("div.yc-anat__k", { text: ANAT_LABEL[row.key] || row.label }),
        h("div.yc-anat__v",
          h("span.disp.disp--sm", { text: String(row.earned) }),
          h("span.disp.disp--sm.is-quiet", { text: `/${row.max}` })),
        h("div.yc-anat__b", inst.hairlineBar(row.earned, row.max))));
    }
  }

  /* ═══ YC-10 · The page patients see ═══════════════════════════════════════════
     Replaces the raw dark Google screenshot. Built from our own components out of
     the real block sequence, so it belongs to the light system instead of fighting
     it — and the clinic's ABSENCE is rendered as a literal dashed gap.

     Honest framing: 29 of 34 clinics share the same proof query and only five
     pages exist, so the copy names the query and never claims this is per-clinic
     evidence. */
  app.register({
    id: "yc10-serp", page: "clinic", size: "panel", subject: true, tools: true,
    title: "The page patients see",

    mount(body, ctx, slots) {
      const col = h("div.serp.grow");
      const note = h("p.caveat");
      body.append(col, note);
      const api = { col, note, tools: slots.tools, panel: slots.panel, query: null };
      drawSerp(api, ctx);
      return api;
    },
    update: drawSerp,
  });

  function drawSerp(api, ctx) {
    const c = ctx.subject;
    const pages = ((ctx.D.serp || {}).pages) || {};
    const queries = Object.keys(pages);
    // No web dataset, no pages, or no proof for this clinic -> the card has
    // nothing honest to say and is hidden rather than emptied.
    if (!setShown(api, ctx.D.web_available !== false && queries.length > 0 && !!(c && c.proof))) {
      return;
    }

    const preferred = (c.proof && c.proof.query) || queries[0];
    if (!api.query || !pages[api.query]) api.query = pages[preferred] ? preferred : queries[0];

    if (api.tools) {
      api.tools.textContent = "";
      api.tools.append(inst.stepper(
        queries.map((q) => ({ label: q, value: q })), api.query,
        (q) => { api.query = q; drawSerp(api, app.context()); },
        { label: "Choose a result page", chars: 22 }));
    }

    const rows = pages[api.query] || [];
    // Absence must also account for the extraction MISSING a mapping. If a row's
    // visible title names the clinic, it IS on the page whether or not map_block
    // resolved it — printing "you are not here" directly above the clinic's own
    // visible row is the worst thing this card could do.
    const present = rows.some((r) => r.mapped_key === c.key || titleNames(r, c));

    api.col.textContent = "";
    let ghostPlaced = false;
    rows.forEach((r) => {
      // Drop the ghost where the clinic *would* sit: just after the local pack.
      if (!present && !ghostPlaced && r.type === "organic") {
        api.col.append(ghostRow(c));
        ghostPlaced = true;
      }
      api.col.append(serpRow(r, c));
    });
    if (!present && !ghostPlaced) api.col.append(ghostRow(c));

    const mine = rows.filter((r) => r.mapped_key).length;
    const strength = (c.proof && c.proof.strength) || null;
    api.note.textContent =
      `The Google results page for “${api.query}”, redrawn from what we read` +
      (strength ? ` — demand ${strength} of 10` : "") + ". " +
      `${mine} of ${rows.length} results belong to a Guntur clinic. ` +
      (present ? "You are on this page." : "You are not on this page.");
  }

  /** Does this result row visibly name the clinic, even though it went unmapped?
   *  Mirrors the token rule modules/web_collector.py uses, minus the generics. */
  function titleNames(row, clinic) {
    const hay = `${row.title || ""} ${row.domain || ""}`.toLowerCase();
    if (!hay.trim()) return false;
    const stop = new Set(["clinic", "clinics", "skin", "hair", "care", "doctor", "the",
                          "and", "centre", "center", "hospital", "derma", "dermatology",
                          "dermatologist", "cosmetic", "laser", "guntur", "best", "top",
                          "near", "treatment", "specialist"]);
    const tokens = String(clinic.display_name || "").toLowerCase()
      .split(/[^a-z0-9]+/).filter((t) => t.length > 3 && !stop.has(t));
    if (!tokens.length) return false;
    const hits = tokens.filter((t) => hay.includes(t)).length;
    return hits >= Math.min(2, tokens.length);
  }

  const KIND_LABEL = { own_clinic: "clinic site", aggregator: "directory",
                       social: "social", borrowed: "listing", other: "out of market" };
  const TYPE_LABEL = { sponsored_top: "Ad", sponsored_mid: "Ad", places: "Map pack",
                       organic: "", ai_overview: "AI answer" };

  function serpRow(r, subject) {
    const isYou = subject && r.mapped_key === subject.key;
    const row = h("div.serprow" + (isYou ? ".is-you" : ""));
    // A SERP position is a rank, so it SPANS: display-light, never dot-matrix.
    row.append(h("span.serprow__pos.disp.disp--xs",
                 { text: r.position === null ? "–" : String(r.position) }));
    const main = h("div.serprow__main",
      h("div.serprow__title", { text: short(inst.displayName(r.clinic || r.title || r.domain) || "—", 64) }));
    const meta = h("div.serprow__meta");
    if (TYPE_LABEL[r.type]) meta.append(h("span.tag.tag--type", { text: TYPE_LABEL[r.type] }));
    meta.append(h("span.swatch", { style: { background: `var(--kind-${r.kind})` } }));
    meta.append(h("span", { text: KIND_LABEL[r.kind] || r.kind }));
    if (r.domain) meta.append(h("span.serprow__dom", { text: r.domain }));
    main.append(meta);
    row.append(main);
    // Not lime: the page's three limes are spent on 03, 04 and 19.
    if (isYou) row.append(h("span.pill", { text: "you" }));
    return row;
  }

  function ghostRow(c) {
    return h("div.serprow.serprow--ghost", {
      "aria-label": `${c ? c.display_name : "This clinic"} does not appear on this page`,
    },
      h("span.serprow__pos.disp.disp--xs", { text: "—" }),
      h("div.serprow__main",
        h("div.serprow__title", { text: c ? c.display_name : "Your clinic" }),
        h("div.serprow__meta",
          h("span", { text: "not on this page — a patient searching this never sees you" }))));
  }

  /* ═══ YC-11 · Who's there instead ═════════════════════════════════════════════
     The four names that hold the page the clinic is missing from. `proof.present`
     has shipped since v2 and was never rendered. It is a flat array of strings
     with no kind on it, so the kind is DERIVED here: against the market's own
     names first, then the aggregator and social sets, then "out of market". */
  const AGGREGATORS = new Set(["practo", "justdial", "just dial", "lybrate", "sulekha",
                               "quikr", "indiamart", "yellowpages", "medindia", "credihealth",
                               "bajajfinservhealth", "askapollo", "curofy"]);
  const SOCIALS = new Set(["instagram", "facebook", "youtube", "twitter", "x", "linkedin"]);

  app.register({
    id: "yc11-competitors", page: "clinic", size: "tall", subject: true,
    title: "Who's there instead", sub: "on that page",

    mount(body, ctx, slots) {
      const list = h("div.stack.yc-rivals.grow");
      body.append(list);
      const api = { list, panel: slots.panel };
      drawRivals(api, ctx);
      return api;
    },
    update: drawRivals,
  });

  function kindOfName(raw, nameIndex) {
    const t = String(raw || "").trim().toLowerCase();
    if (nameIndex.has(t)) return "own_clinic";
    const bare = t.replace(/^www\./, "").split(".")[0];
    if (AGGREGATORS.has(t) || AGGREGATORS.has(bare)) return "aggregator";
    if (SOCIALS.has(t) || SOCIALS.has(bare)) return "social";
    return "other";
  }

  function drawRivals(api, ctx) {
    const c = ctx.subject;
    const present = (c && c.proof && c.proof.present) || [];
    if (!setShown(api, ctx.D.web_available !== false && present.length > 0)) return;

    const nameIndex = new Map();
    for (const x of ctx.all) {
      nameIndex.set(String(x.name || "").toLowerCase(), x.key);
      nameIndex.set(String(x.display_name || "").toLowerCase(), x.key);
    }

    api.list.textContent = "";
    present.forEach((raw) => {
      const kind = kindOfName(raw, nameIndex);
      // The raw Maps names run to 125 keyword-stuffed characters; the same
      // cleanup build_web._display_name does server-side happens here.
      const name = short(inst.displayName(raw), 30);
      api.list.append(h("div.yc-rival", { title: String(raw) },
        h("span.swatch", { style: { background: `var(--kind-${kind})` } }),
        h("span.yc-rival__n", { text: name }),
        h("span.yc-rival__k", { text: KIND_LABEL[kind] })));
    });
  }

  /* ═══ YC-12 · Intent polar ════════════════════════════════════════════════════
     A hand-drawn 6-spoke polar. An ECharts radar reads as a template; this one
     degrades honestly — a category the clinic never appears in renders as a dead
     stub rather than a zero-length spoke that looks like data.

     v3's click-to-filter is DELETED here: Your Clinic is static-read, and MK-15
     keeps the category toggle on the page it actually filters. */
  app.register({
    id: "yc12-polar", page: "clinic", size: "tall", subject: true,
    title: "Where patients look", sub: "average position by intent",

    mount(body, ctx) {
      const host = h("div.polar-host.yc-polar");
      const note = h("p.caveat");
      body.append(host, note);
      const api = { host, note };
      drawPolar(api, ctx);
      return api;
    },
    update: drawPolar,
  });

  function drawPolar(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const market = ctx.D.intents_market || {};
    const cats = Object.keys(market);
    if (!cats.length) { api.host.textContent = ""; api.note.textContent = ""; return; }

    const mine = new Map((c.intents || []).map((i) => [i.cat, i]));
    api.host.textContent = "";
    api.host.append(inst.polar(cats, market, mine, {
      size: 240, radius: 66, labelR: 92,
      ariaLabel: `Average search position by patient intent. You appear in ` +
                 `${mine.size} of ${cats.length} intent groups.`,
    }));

    const seen = mine.size, missing = cats.length - seen;
    api.note.textContent = seen === 0
      ? "Not seen in any tracked search category."
      : missing
        ? `Further out is better. You appear in ${seen} of ${cats.length} groups; the ` +
          `${missing} short stubs are searches you never show up for.`
        : "Further out is better. The dashed ring is the market median.";
  }

  /* ═══ YC-13 · Your web ground ═════════════════════════════════════════════════
     Owned versus borrowed blocks, the platforms carrying you, and the best
     organic position you hold. Twenty of the 34 clinics own nothing and borrow
     nothing, so the empty read is the common one and has to be a sentence rather
     than three zeroes. `web.best_position` has shipped since v2, unread. */
  app.register({
    id: "yc13-web-ground", page: "clinic", size: "stat", subject: true,
    title: "Your web ground",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap, panel: slots.panel };
      drawGround(api, ctx);
      return api;
    },
    update: drawGround,
  });

  function drawGround(api, ctx) {
    const c = ctx.subject;
    if (!setShown(api, ctx.D.web_available !== false && !!c)) return;
    const w = c.web || {};
    const owned = w.owned || 0, borrowed = w.borrowed || 0;
    const platforms = w.platforms || [];
    const nothing = !owned && !borrowed && !platforms.length;

    api.wrap.textContent = "";
    api.wrap.append(h("div.yc-pair",
      h("div.yc-pair__cell",
        h("span.disp.disp--sm", { text: String(owned) }),
        h("span.yc-pair__k.is-owned", { text: "owned blocks" })),
      h("div.yc-pair__cell",
        h("span.disp.disp--sm", { text: String(borrowed) }),
        h("span.yc-pair__k.is-borrowed", { text: "borrowed" }))));

    if (nothing) {
      api.wrap.append(h("p.metric__c", { text: "Not seen on the open web yet." }));
    } else if (platforms.length) {
      api.wrap.append(h("div.row.yc-chips",
        platforms.map((p) => inst.pill(inst.platformLabel(p)))));
    } else {
      // The ladder report.py's own scorecard walks, reused as caption logic.
      api.wrap.append(h("p.metric__c", {
        text: w.has_own_site ? "Your own site ranks." : "Paid placement only.",
      }));
    }

    const best = w.best_position;
    api.wrap.append(h("div.yc-best",
      h("span.disp.disp--xs", { text: best === null || best === undefined ? "never" : `#${best}` }),
      h("span.unit", { text: "best organic position" })));
  }

  /* ═══ YC-14 · Reviews vs the market ═══════════════════════════════════════════
     One dumbbell, you against the median. The market runs 22 to 2,085 reviews, so
     the track is square-rooted — a linear scale puts 31 of the 34 clinics inside
     the first sixth of it. */
  app.register({
    id: "yc14-reviews", page: "clinic", size: "stat", subject: true,
    title: "Reviews vs the market",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap, panel: slots.panel };
      drawReviews(api, ctx);
      return api;
    },
    update: drawReviews,
  });

  function drawReviews(api, ctx) {
    const c = ctx.subject;
    if (!setShown(api, ctx.D.reviews_available !== false && !!c)) return;
    // The payload's canonical median — never recomputed here, or the clinic view
    // and the market view would quote two different "typical" clinics.
    const med = (ctx.D.kpis || {}).median_reviews || 0;
    const you = c.reviews || 0;

    api.wrap.textContent = "";
    api.wrap.append(h("div.yc-pair",
      h("div.yc-pair__cell",
        h("span.disp.disp--sm", { text: num(you) }),
        h("span.yc-pair__k", { text: "you" })),
      h("div.yc-pair__cell",
        h("span.disp.disp--sm.is-quiet", { text: num(med) }),
        h("span.yc-pair__k", { text: "market median" }))));
    api.wrap.append(h("div.yc-dumbhost", inst.dumbbell(you, med, { scale: "sqrt" })));
    api.wrap.append(h("p.caveat", {
      text: you >= med ? "Ahead of the typical Guntur clinic."
                       : "Behind the typical Guntur clinic.",
    }));
  }

  /* ═══ YC-15 · Sponsored presence ══════════════════════════════════════════════
     A filament against the market leader. The point of the instrument is how
     little is lit: 27 of 34 clinics never appeared as an ad on any page we read,
     and a zero here is the card's whole argument, not an empty state.

     `sponsored` counts ad APPEARANCES on captured pages. We cannot see spend, so
     the copy never says "bought". */
  app.register({
    id: "yc15-sponsored", page: "clinic", size: "stat", subject: true,
    title: "Sponsored presence",

    mount(body, ctx) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap };
      drawSponsored(api, ctx);
      return api;
    },
    update: drawSponsored,
  });

  function drawSponsored(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const n = c.sponsored || 0;
    const leader = Math.max(1, ...ctx.all.map((x) => x.sponsored || 0));
    const nQ = serpQueries(ctx.D);

    api.wrap.textContent = "";
    api.wrap.append(h("div.yc-hero",
      h("span.disp.disp--sm", { text: String(n) }),
      h("span.unit", { text: `/${nQ} result pages` })));
    api.wrap.append(h("div.yc-filhost", inst.filament(n / leader, { color: "var(--data-borrowed)" })));
    api.wrap.append(h("p.metric__c", {
      text: `You appeared as an ad on ${n} of the ${nQ} result pages we read. ` +
            `The busiest advertiser in Guntur appeared on ${leader}.`,
    }));
  }

  /* ═══ YC-16 · Where you sit ═══════════════════════════════════════════════════
     The only geography on this page. Not a slippy map — no tiles, no network,
     ~0 KB: every clinic as a dot in normalised lat/lng with distance rings from
     the city core, running off the card's bottom edge.

     v3's pointermove/click bus wiring is DELETED — this page no longer selects. */
  app.register({
    id: "yc16-location", page: "clinic", size: "stat", subject: true,
    title: "Where you sit",

    mount(body, ctx) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap };
      drawWhere(api, ctx);
      return api;
    },
    update: drawWhere,
  });

  function drawWhere(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const pts = ctx.all.filter((x) => x.lat !== null && x.lng !== null)
      .map((x) => ({
        key: x.key, lat: x.lat, lng: x.lng, band: store.bandOf(x.visibility),
        you: !!(c && x.key === c.key),
        title: `${x.display_name} · visibility ${x.visibility} · ${x.km_core} km from the core`,
      }));
    const located = c.km_core !== null && c.km_core !== undefined && c.lat !== null;

    api.wrap.textContent = "";
    api.wrap.append(h("div.yc-hero",
      h("span.disp.disp--md", { text: located ? c.km_core.toFixed(1) : "—" }),
      h("span.unit", { text: located ? "km from the city core" : "location not resolved" })));
    if (!pts.length) return;
    api.wrap.append(inst.edgeCrop(
      inst.miniMap(pts, { width: 300, height: 150, pad: 16, core: CORE,
                          dotR: 4, youR: 6.5, coreR: 3, ringLabels: false, keyed: false,
                          ariaLabel: "Clinic locations around the Guntur city core" }),
      { class: "yc-crop--map" }));
  }

  /* ═══ YC-17 · Patient voice ═══════════════════════════════════════════════════
     One dot per review actually read, with deterministic jitter. The sample size
     is printed rather than hidden: ten reviews is a sample, not a trend, and the
     caption says so with the real n — which is 20 for two clinics, so it is never
     hardcoded. */
  app.register({
    id: "yc17-voice", page: "clinic", size: "half", dense: true, subject: true,
    title: "Patient voice",

    mount(body, ctx, slots) {
      const wrap = h("div.yc-voice");
      body.append(wrap);
      const api = { wrap, panel: slots.panel };
      drawVoice(api, ctx);
      return api;
    },
    update: drawVoice,
  });

  function drawVoice(api, ctx) {
    const c = ctx.subject;
    if (!setShown(api, ctx.D.reviews_available !== false && !!c)) return;
    const n = c.nlp;
    api.wrap.textContent = "";
    if (!n || !n.n) {
      api.wrap.append(h("p.metric__c", { text: "No reviews read yet." }));
      return;
    }
    const total = n.n;
    const pos = Math.round(((n.pos || 0) / 100) * total);

    api.wrap.append(h("div.yc-voice__l",
      h("div.yc-hero",
        h("span.disp.disp--md", { text: `${Math.round(n.pos || 0)}%` }),
        h("span.unit", { text: "positive" })),
      h("p.caveat", { text: `From your ${total} most recent reviews.` })));
    api.wrap.append(h("div.yc-voice__r",
      inst.jitterGrid(total, pos, c.key, { per: 10, cell: 14, r: 4.6, scale: 1.5 }),
      h("p.metric__c", { text: `${pos} of ${total} reviews read were positive.` })));
  }

  /* ═══ YC-18 · Praised / flagged ═══════════════════════════════════════════════
     The themes either side of the sentiment. Pains are empty for 23 of the 31
     clinics with NLP, so the flagged half needs a sentence rather than a blank
     row — "nothing flagged" is a result, not a missing value.
     `nlp.recent6mo` has shipped since v2 and was never read. */
  app.register({
    id: "yc18-themes", page: "clinic", size: "half", subject: true,
    title: "Praised / flagged",

    mount(body, ctx, slots) {
      const wrap = h("div.stack.grow");
      body.append(wrap);
      const api = { wrap, panel: slots.panel };
      drawThemes(api, ctx);
      return api;
    },
    update: drawThemes,
  });

  function drawThemes(api, ctx) {
    const c = ctx.subject;
    if (!setShown(api, ctx.D.reviews_available !== false && !!c)) return;
    const n = c.nlp;
    api.wrap.textContent = "";
    if (!n || !n.n) {
      api.wrap.append(h("p.metric__c", { text: "No reviews read yet." }));
      return;
    }
    api.wrap.append(
      inst.pillRow("Praised", n.themes || [], null, `nothing stood out in these ${n.n}`),
      inst.pillRow("Watch-outs", n.pains || [], "warn", `nothing flagged in these ${n.n}`));

    api.wrap.append(h("div.yc-two",
      h("div.yc-two__c",
        h("span.disp.disp--xs", { text: pct(n.referral || 0, 0) }),
        h("span.unit", { text: "mention being referred" })),
      h("div.yc-two__c",
        h("span.disp.disp--sm", { text: String(n.recent6mo === null || n.recent6mo === undefined ? 0 : n.recent6mo) }),
        h("span.unit", { text: "of them from the last 6 months" }))));

    api.wrap.append(h("p.caveat", { text: `From your ${n.n} most recent reviews.` }));
  }

  /* ═══ YC-19 · The prescription ════════════════════════════════════════════════
     The action surface, on the dark rung. Each dose is a nested tile carrying a
     dose gauge, the action, and the projected RANK move — the single most
     persuasive number in the product. Toggling a dose recomputes the projection,
     which is what makes this a tool rather than a list.

     The full-plan figure is framed as a CEILING, never a forecast: close every
     gap and 27 of the 34 clinics land on exactly (100, #2). */
  app.register({
    id: "yc19-prescription", page: "clinic", size: "band", rung: "dark", subject: true,
    title: "The prescription", sub: "what to fix, and what it moves",

    mount(body, ctx) {
      const head = h("div.yc-rx__head");
      const list = h("div.yc-rx__stack");
      body.append(head, list);
      const api = { head, list, off: new Set() };
      drawPlan(api, ctx);
      return api;
    },
    update(api, ctx) { api.off.clear(); drawPlan(api, ctx); },
  });

  function drawPlan(api, ctx) {
    const c = ctx.subject;
    const plan = c && c.plan;
    api.head.textContent = "";
    api.list.textContent = "";
    if (!plan) return;

    if (atCeiling(c)) {
      api.head.append(h("p.panel__note", { text: AT_CEILING }));
      return;
    }

    const chosen = plan.steps.filter((st) => !api.off.has(st.key));
    // Points are additive per step; the compound figure from the payload is the
    // authority when the whole plan is selected.
    const projected = chosen.length === plan.steps.length
      ? plan.compound.all.vis
      : Math.min(100, plan.now.vis + chosen.reduce((a, st) => a + st.lift, 0));
    const projRank = chosen.length === plan.steps.length ? plan.compound.all.rank
      : (chosen.length ? estimateRank(ctx, projected) : plan.now.rank);
    const label = chosen.length === plan.steps.length ? "with every gap closed"
      : (chosen.length ? "with what you have selected" : "with nothing selected");

    api.head.append(
      // A family marker, not a hero — the chip carries no numeral, which is what
      // keeps the page's dot-white budget at one (YC-01) while the jewel census
      // reads three.
      h("span.jewel.jewel--action.jewel--chip", { "aria-hidden": "true" }),
      h("div.yc-rx__span",
        inst.deltaSpan(`#${plan.now.rank}`, `#${projRank}`, { size: "sm" }),
        h("div.metric__c", { text: `${label} · visibility ${plan.now.vis} → ${projected} of 100` })),
      h("div.yc-rx__ruler", projRuler(plan.now.vis, projected)),
      h("p.caveat.yc-rx__caveat", {
        text: `Closing every gap tops out at #${plan.compound.all.rank} of ${c.visibility_total} — ` +
              `that is the arithmetic ceiling for any clinic in this market, not a forecast. ` +
              `Your first two fixes alone reach #${plan.compound.top2.rank}.`,
      }));

    plan.steps.forEach((step) => {
      const on = !api.off.has(step.key);
      const card = h("div.inner.yc-dose" + (on ? "" : ".is-off"));
      card.append(h("div.yc-dose__g", { "aria-hidden": "true" }, inst.doseGauge(step.lift)));
      const mid = h("div.yc-dose__m",
        h("div.yc-dose__a", { text: RX_COPY[step.key] || step.label }),
        h("div.metric__c", { text: RX_WHY[step.key] || "" }),
        h("div.yc-dose__move",
          inst.deltaSpan(`#${plan.now.rank}`, `#${step.rank_after}`, { size: "xs" }),
          h("span.yc-dose__pts",
            h("span.disp.disp--sm", { text: `+${step.lift}` }),
            h("span.unit", { text: "points" }))),
        h("button.yc-dose__t", {
          type: "button", text: on ? "in the plan" : "add",
          "aria-pressed": String(on),
          "aria-label": `${on ? "Remove" : "Add"} ${RX_COPY[step.key] || step.label}`,
          onclick: () => {
            if (api.off.has(step.key)) api.off.delete(step.key); else api.off.add(step.key);
            drawPlan(api, app.context());
          },
        }));
      card.append(mid);
      api.list.append(card);
    });
  }

  const RX_COPY = {
    website: "Build a website patients can land on",
    search: "Get that site ranking in Google search",
    maps: "Win a place in the local map box",
    reviews: "Close the Google reviews gap",
    phone: "Publish a number patients can call",
    breadth: "Show up across more of the searches patients run",
  };
  const RX_WHY = {
    website: "A patient who Googles you has nowhere of yours to land.",
    search: "Directories are capturing patients searching your treatments.",
    maps: "The map box is the first thing on the page locally.",
    reviews: "Reviews are the trust signal patients read first.",
    phone: "The last step before a booking is a dead end.",
    breadth: "You show up for a narrow slice of what patients ask.",
  };

  /** Estimate the rank a projected score would earn, against the unchanged market. */
  function estimateRank(ctx, vis) {
    return ctx.all.filter((x) => x.key !== ctx.subject.key)
      .map((x) => x.visibility || 0)
      .filter((v) => v > vis).length + 1;
  }

  /**
   * The shared projection ruler. v3 drew `now` and `goal` as 3×full-height rects
   * — which are LINES, and the v4 law is that every marker is a glowing point.
   * Both are dots here; the "now" dot is the page's third and last lime.
   */
  function projRuler(now, after) {
    const a = clamp(now, 0, 100), b = clamp(after, 0, 100);
    return h("div.ruler.yc-proj", { "aria-hidden": "true" },
      inst.tickRuler(21, null, { height: 24 }),
      h("i.yc-proj__span", { style: { left: `${Math.min(a, b)}%`,
                                      width: `${Math.abs(b - a)}%` } }),
      h("i.ruler__dot.yc-proj__now", { style: { left: `${a}%` } }),
      h("i.ruler__dot.yc-proj__goal", { style: { left: `${b}%` } }));
  }
})(window.DI);
