/* ── "Your Clinic" panels ──────────────────────────────────────────────────────
   Layout, in grid order:
     P1 twin jewels  7 naked   P2 split-score   5 naked
     P3 examination  7×2       P4 intent polar  5×2
     P5 redrawn SERP 12
     P6 prescription 7×2       P7 patient voice 5   P8 constellation 5
   Spans are 7/5 and 12 — never 6/6, which is the tell of a generated layout. */
(function (DI) {
  "use strict";

  const { h, s, inst, store, bus, app, num, pct, clamp, short } = DI;

  const bandLabel = (b) => ({ alarm: "Nearly invisible", caution: "Below market",
                              steady: "Partway there", clear: "Strong" }[b] || "");

  /* ═══ P1 · Twin jewels ═══════════════════════════════════════════════════════
     The hero. The visibility jewel STATE-MAPS — its recipe follows the score
     band, so a 34 renders in caution and can never read as reassuring. The rank
     jewel never state-maps: a rank is an index, not a condition.
     Hovering a column cross-filters the canvas, so the hero is also a control. */
  app.register({
    id: "twin-jewels", page: "clinic", span: 7, card: false, subject: true,

    mount(body, ctx) {
      const wrap = h("div.jewel-pair");
      body.append(wrap);
      const api = { wrap };
      drawJewels(api, ctx);
      wrap.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "twin-jewels");
      });
      wrap.addEventListener("pointerleave", () => bus.hover(null, "twin-jewels"));
      wrap.addEventListener("click", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        if (n && store.select(n.dataset.clinic)) bus.emit("select", { key: n.dataset.clinic });
      });
      return api;
    },
    update(api, ctx) { drawJewels(api, ctx); },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  function drawJewels(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const sorted = ctx.all.slice().sort((a, b) => (a.visibility || 0) - (b.visibility || 0));
    const idx = sorted.findIndex((x) => x.key === c.key);
    const band = store.bandOf(c.visibility);
    const total = c.visibility_total || ctx.all.length;

    api.wrap.textContent = "";
    api.wrap.append(
      inst.jewel({
        family: band, label: "Online visibility", value: c.visibility,
        sub: `${bandLabel(band)} · ${c.visibility_rank} of ${total} in Guntur`,
        viz: inst.dotColumn(sorted.map((x) => x.visibility || 0),
                            { highlight: idx, keys: sorted.map((x) => x.key), height: 46 }),
        ariaLabel: `Online visibility ${c.visibility} of 100. ${bandLabel(band)}. Ranked ${c.visibility_rank} of ${total}.`,
      }),
      inst.jewel({
        family: "index", label: "Market rank", value: c.visibility_rank,
        sub: `of ${total} in Guntur`,
        viz: inst.tickRuler(total, (c.visibility_rank - 1) / Math.max(1, total - 1), { height: 26 }),
        ariaLabel: `Ranked ${c.visibility_rank} of ${total} clinics in Guntur.`,
      }));
  }

  /* ═══ P2 · Split-score stack ═════════════════════════════════════════════════
     Naked on the field. Opens the black box: the published score is 60% Maps +
     40% web, and until now only the blended number shipped. */
  app.register({
    id: "split-score", page: "clinic", span: 5, card: false, subject: true,

    mount(body, ctx) {
      const wrap = h("div.stack.split");
      body.append(wrap);
      const api = { wrap };
      drawSplit(api, ctx);
      return api;
    },
    update(api, ctx) { drawSplit(api, ctx); },
  });

  function drawSplit(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    // maps_score and web_score are GAP measures: higher means more ground to make
    // up. The visibility jewel beside this panel runs the other way (higher is
    // better), so these are labelled "gap" explicitly and carry the caution hue —
    // never green, which would read as "good" on the worse number.
    const maps = c.maps_score, web = c.web_score;
    const worst = (web !== null && maps !== null && web > maps) ? "web" : "maps";

    api.wrap.textContent = "";

    const bar = h("div.blendbar", { "aria-hidden": "true" },
      h("i.blendbar__maps", { style: { width: "60%", "--fill": `${maps === null ? 0 : maps}%` } }),
      h("i.blendbar__web", { style: { width: "40%", "--fill": `${web === null ? 0 : web}%` } }));

    api.wrap.append(h("div.split__row",
      h("div.row",
        inst.metric({ value: maps === null ? "—" : maps, pill: "Maps gap · 60%",
                      lime: worst === "maps", caption: null }),
        inst.metric({ value: web === null ? "—" : web, pill: "Web gap · 40%",
                      lime: worst === "web", caption: null })),
      bar,
      h("div.metric__c", {
        text: `Both run 0–100, and higher means more ground to make up. Weighted 60/40 they ` +
              `give an opportunity score of ${c.score}.`,
      })));

    // Average Maps position SPANS, so it takes the light register, not dot-matrix.
    const pos = c.pos_avg;
    const posRow = h("div.split__row.split__crop",
      h("div.row",
        h("span.disp", { text: pos === null ? "—" : pos.toFixed(1) }),
        h("span.unit", { text: "average position on Google Maps" })),
      h("div.metric__c", { text: pos === null ? "not seen in the Maps pack"
        : (pos <= 3 ? "top of the pack" : pos <= 7 ? "mid-pack" : "buried below the fold") }));
    if (pos !== null) {
      const crop = h("div.edge-crop", { "aria-hidden": "true" },
        inst.tickRuler(30, clamp((pos - 1) / 14, 0, 1), { height: 20 }));
      posRow.append(crop);
    }
    api.wrap.append(posRow);

    api.wrap.append(h("div.split__row",
      inst.metric({
        value: c.high_intent === null ? "—" : Math.round(c.high_intent * 100),
        unit: c.high_intent === null ? null : "%",
        caption: "of your demand is ready to book — pricing, appointment and near-me searches",
      })));
  }

  /* ═══ P3 · The examination — instrument rack ═════════════════════════════════
     Five checks, FIVE DIFFERENT INSTRUMENTS. v2 rendered five identical grey
     rounded rectangles differentiated only by a status pill, which is why it read
     as a disabled form rather than a diagnostic.

     Status is carried by FILL and ALPHA. The only hue in the rack is one caution
     accent on the weakest row. */

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
    id: "examination", page: "clinic", span: 7, rows: 2, subject: true,
    title: "The examination", sub: "five checks, five instruments",

    mount(body, ctx) {
      const rack = h("div.rack");
      body.append(rack);
      const api = { rack };
      drawRack(api, ctx);
      rack.addEventListener("click", (e) => {
        const row = e.target.closest && e.target.closest(".irow");
        if (row && row.dataset.check) openCheckDrawer(row.dataset.check, app.context());
      });
      return api;
    },
    update(api, ctx) { drawRack(api, ctx); },
  });

  function drawRack(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const web = c.web || {};
    const D = ctx.D;
    const nSerp = ((D.serp || {}).ownership || {}).totals || {};
    const serpQueries = nSerp.queries || 78;
    const medianReviews = (D.kpis || {}).median_reviews || 0;
    const meanReviews = (D.kpis || {}).avg_reviews || 0;

    api.rack.textContent = "";
    for (const check of (c.scorecard || [])) {
      const copy = CHECK_COPY[check.key] || { label: check.label, why: "" };
      const weak = check.status === "bad";
      const value = valueFor(check, web, serpQueries, c, medianReviews);
      const note = noteFor(check, c, medianReviews, meanReviews);
      const row = h("div.irow", {
        data: { check: check.key }, role: "button", tabindex: "0",
        // The accessible name must carry the SAME corrected copy the sighted row
        // shows, not report.py's raw string, or the two disagree.
        "aria-label": `${copy.label}: ${value}. ${note}`,
      });
      row.append(h("div.irow__k", copy.label, h("small", { text: copy.why })));
      row.append(h("div.irow__i", instrumentFor(check, c, web, serpQueries,
                                                medianReviews, meanReviews)));
      row.append(h("div.irow__v" + (weak ? ".is-weak" : ""), { text: value }));
      api.rack.append(row);
    }
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

  function valueFor(check, web, serpQueries, c, medianReviews) {
    if (check.key === "maps") return `${web.in_places || 0} of ${serpQueries}`;
    // The instrument plots against the MEDIAN, so the number beside it must too —
    // report.py's own string quotes the mean and would contradict the dumbbell.
    if (check.key === "reviews") return `${num(c.reviews)} vs ${num(medianReviews)} median`;
    if (check.key === "search") return web.has_own_site ? "your site ranks"
      : (web.owned > 0 ? "paid placement only"
        : (web.borrowed > 0 ? "directories only" : "not found"));
    return check.value;
  }

  /** One instrument per check — the point of the panel. */
  function instrumentFor(check, c, web, serpQueries, medianReviews, meanReviews) {
    const good = check.status === "good";
    switch (check.key) {
      case "website":
      case "phone":
        // A filament: lit when present, a broken ghost when not. No status chip.
        return good
          ? inst.filament(1, { color: "var(--data-owned)" })
          : h("div.filament.filament--broken", { "aria-hidden": "true" });

      case "search": {
        // A 78-dot census: lit where the clinic's own site ranks, half-lit where
        // a directory carries it, dead where it is absent. This is where the
        // 1122-block corpus finally shows up in the clinic view.
        const owned = web.owned || 0, borrowed = web.borrowed || 0;
        return dotCensus(serpQueries, owned, borrowed);
      }

      case "maps": {
        // A tick ruler with a filled span 0 -> in_places/queries.
        const frac = clamp((web.in_places || 0) / Math.max(1, serpQueries), 0, 1);
        return h("div.spanruler",
          inst.tickRuler(28, null, { height: 18 }),
          h("i.spanruler__fill", { style: { width: `${frac * 100}%` } }));
      }

      case "reviews":
        // A dumbbell against the MEDIAN, with the skewed mean drawn as a ghost
        // tick so the honest comparator is the one that reads loudest.
        return dumbbell(c.reviews || 0, medianReviews, meanReviews);

      default:
        return h("div");
    }
  }

  function dotCensus(total, owned, borrowed) {
    const cols = Math.min(total, 78);
    const per = 26, rows = Math.ceil(cols / per);
    const cell = 7, r = 2.1;
    const w = per * cell, hgt = rows * cell + 2;
    const dots = [];
    for (let i = 0; i < cols; i++) {
      const x = (i % per) * cell + cell / 2;
      const y = Math.floor(i / per) * cell + cell / 2 + 1;
      const state = i < owned ? "own" : (i < owned + borrowed ? "borrowed" : "none");
      dots.push(s("circle", {
        cx: x.toFixed(1), cy: y.toFixed(1), r,
        class: `census census--${state}`,
      }));
    }
    return s("svg", { class: "viz census-viz", viewBox: `0 0 ${w} ${hgt}`,
                      height: hgt * 1.6, preserveAspectRatio: "xMinYMid meet",
                      "aria-hidden": "true" }, dots);
  }

  function dumbbell(you, median, mean) {
    const hi = Math.max(you, median, mean) * 1.12 || 1;
    const px = (v) => clamp(v / hi, 0, 1) * 100;
    return h("div.dumb", { "aria-hidden": "true" },
      h("i.dumb__track"),
      h("i.dumb__ghost", { style: { left: `${px(mean)}%` }, title: `market mean ${Math.round(mean)}` }),
      h("i.dumb__line", { style: { left: `${Math.min(px(you), px(median))}%`,
                                   width: `${Math.abs(px(you) - px(median))}%` } }),
      h("i.dumb__mkt", { style: { left: `${px(median)}%` } }),
      h("i.dumb__you", { style: { left: `${px(you)}%` } }));
  }

  function openCheckDrawer(key, ctx) {
    const c = ctx.subject;
    const check = (c.scorecard || []).find((x) => x.key === key);
    if (!check) return;
    const copy = CHECK_COPY[key] || {};
    const kpis = ctx.D.kpis || {};
    app.openDrawer(copy.label || check.label, (b) => {
      // Same corrected copy as the row — three surfaces, one statement.
      b.append(h("p.panel__note", {
        text: noteFor(check, c, kpis.median_reviews || 0, kpis.avg_reviews || 0),
      }));
      const step = (c.plan && c.plan.steps || []).find((x) => x.key === key);
      if (step) {
        b.append(h("div.inner",
          h("div.metric__c", { text: "Closing this one gap" }),
          h("div.row", h("span.disp", { text: `#${c.visibility_rank} → #${step.rank_after}` })),
          h("div.metric__c", { text: `visibility ${c.visibility} → ${step.vis_after} (+${step.lift})` })));
      }
      if (key === "reviews") {
        const above = (ctx.all || []).filter((x) => (x.reviews || 0) > (kpis.avg_reviews || 0)).length;
        b.append(h("p.caveat", {
          text: `The dumbbell plots you against the median (${num(kpis.median_reviews)}); the faint tick ` +
                `is the mean (${num(kpis.avg_reviews)}). Only ${above} of ${(ctx.all || []).length} clinics ` +
                `sit above that mean, which is why the median is the fairer read of a typical clinic.`,
        }));
      }
      if (key === "maps") {
        b.append(h("p.caveat", {
          text: "This measures the local map box across the Google result pages we read — " +
                "not whether you are listed on Google Maps. Every clinic in this report is.",
        }));
      }
    });
  }

  /* ═══ P4 · Where patients look for you ═══════════════════════════════════════
     A hand-drawn 6-spoke polar. An ECharts radar reads as a template; this one
     degrades honestly — a category the clinic never appears in renders as a dead
     stub rather than a zero-length spoke that looks like data. */
  app.register({
    id: "intent-polar", page: "clinic", span: 5, rows: 2, subject: true,
    title: "Where patients look for you", sub: "average position by intent",

    mount(body, ctx) {
      const host = h("div.polar-host");
      const note = h("p.caveat");
      body.append(host, note);
      const api = { host, note };
      drawPolar(api, ctx);
      host.addEventListener("click", (e) => {
        const n = e.target.closest && e.target.closest("[data-cat]");
        if (!n) return;
        store.toggleFacet("category", n.dataset.cat);
        bus.emit("filter", {});
      });
      return api;
    },
    update(api, ctx) { drawPolar(api, ctx); },
  });

  function drawPolar(api, ctx) {
    const c = ctx.subject;
    if (!c) return;
    const market = ctx.D.intents_market || {};
    const cats = Object.keys(market);
    if (!cats.length) { api.host.textContent = ""; return; }

    const mine = new Map((c.intents || []).map((i) => [i.cat, i]));
    const size = 300, cx = size / 2, cy = size / 2 + 6, R = 104;
    // Radius is INVERTED position: #1 sits outermost. Positions run 1..15.
    const rOf = (pos) => R * clamp((15 - pos) / 14, 0.08, 1);
    const ang = (i) => (Math.PI * 2 * i) / cats.length - Math.PI / 2;

    const kids = [];
    // Web rings, quiet.
    for (const f of [0.33, 0.66, 1]) {
      kids.push(s("circle", { cx, cy, r: (R * f).toFixed(1), class: "hair", fill: "none" }));
    }
    // Market median ring — dashed, so it never competes with the clinic.
    const mkt = cats.map((cat, i) => {
      const r = rOf(market[cat]);
      return [cx + r * Math.cos(ang(i)), cy + r * Math.sin(ang(i))];
    });
    kids.push(s("polygon", { class: "polar-mkt",
      points: mkt.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ") }));

    // The clinic's own polygon, using only the spokes it actually appears in.
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
          r: (3 + Math.min(4, Math.sqrt(entry.n))).toFixed(1),
          class: "polar-vertex", data: { cat },
        }, s("title", {}, `${cat} · your average #${entry.pos} from ${entry.n} appearances · market #${market[cat]}`)));
      } else {
        // Dead stub: the loss beat, without inventing a data point.
        const r0 = R * 0.1, r1 = R * 0.22;
        stubs.push(s("line", {
          x1: (cx + r0 * Math.cos(a)).toFixed(1), y1: (cy + r0 * Math.sin(a)).toFixed(1),
          x2: (cx + r1 * Math.cos(a)).toFixed(1), y2: (cy + r1 * Math.sin(a)).toFixed(1),
          class: "polar-stub", data: { cat },
        }, s("title", {}, `${cat} — you never appear here`)));
      }
      // Spoke + label
      kids.push(s("line", { x1: cx, y1: cy, x2: cx + R * Math.cos(a), y2: cy + R * Math.sin(a),
                            class: "hair" }));
      const lx = cx + (R + 26) * Math.cos(a), ly = cy + (R + 26) * Math.sin(a);
      kids.push(s("text", {
        x: lx.toFixed(1), y: ly.toFixed(1),
        "text-anchor": Math.abs(Math.cos(a)) < 0.3 ? "middle" : (Math.cos(a) > 0 ? "start" : "end"),
        "dominant-baseline": "middle", class: "polar-label", data: { cat },
      }, short(cat.replace(" & Social Proof", "").replace(" & Booking", ""), 16)));
    });

    if (pts.length >= 3) {
      kids.push(s("polygon", { class: "polar-you",
        points: pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ") }));
    } else if (pts.length === 2) {
      kids.push(s("line", { class: "polar-you-line",
        x1: pts[0][0].toFixed(1), y1: pts[0][1].toFixed(1),
        x2: pts[1][0].toFixed(1), y2: pts[1][1].toFixed(1) }));
    }
    kids.push(...stubs, ...vertices);

    api.host.textContent = "";
    api.host.append(s("svg", {
      class: "viz polar", viewBox: `0 0 ${size} ${size + 12}`,
      role: "img", "aria-label": "Average search position by patient intent",
    }, kids));

    const seen = mine.size, missing = cats.length - seen;
    api.note.textContent = missing
      ? `Further from the centre is better. You appear in ${seen} of ${cats.length} intent groups; the ${missing} short stubs are searches you never show up for.`
      : `Further from the centre is better. The dashed ring is the market median.`;
  }

  /* ═══ P5 · The page patients actually see ════════════════════════════════════
     Replaces the raw dark Google screenshot. Built from our own components out of
     the real block sequence, so it belongs to the light system instead of fighting
     it — and the clinic's ABSENCE is rendered as a literal dashed gap.

     Honest framing: 29 of 34 clinics share the same proof query and only a handful
     of pages exist, so the copy says "the page patients see for «query»" and never
     claims this is per-clinic evidence. */
  app.register({
    id: "serp-page", page: "clinic", span: 12, subject: true,
    title: "The page patients actually see",

    mount(body, ctx) {
      const stepper = h("div.seg.serp-stepper");
      const head = body.parentElement.querySelector(".panel__head");
      if (head) head.append(h("div.tools", stepper));
      const col = h("div.serp");
      const note = h("p.caveat");
      body.append(col, note);
      const api = { col, note, stepper, query: null };
      drawSerp(api, ctx);
      return api;
    },
    update(api, ctx) { drawSerp(api, ctx); },
  });

  function drawSerp(api, ctx) {
    const c = ctx.subject;
    const pages = ((ctx.D.serp || {}).pages) || {};
    const queries = Object.keys(pages);
    if (!queries.length) { api.col.textContent = ""; return; }

    const preferred = (c.proof && c.proof.query) || queries[0];
    if (!api.query || !pages[api.query]) api.query = pages[preferred] ? preferred : queries[0];

    api.stepper.textContent = "";
    queries.forEach((q) => {
      api.stepper.append(h("button", {
        type: "button", text: short(q, 26), title: q,
        "aria-pressed": String(q === api.query),
        onclick: () => { api.query = q; drawSerp(api, app.context()); },
      }));
    });

    const rows = pages[api.query] || [];
    // Absence must also account for the extraction MISSING a mapping. If a row's
    // visible title names the clinic, it IS on the page whether or not map_block
    // resolved it — printing "you are not here" directly above the clinic's own
    // visible row is the worst thing this panel could do.
    const present = rows.some((r) => r.mapped_key === c.key || titleNames(r, c));

    api.col.textContent = "";
    let ghostPlaced = false;
    rows.slice(0, 14).forEach((r, i) => {
      // Drop the ghost where the clinic *would* sit: just after the local pack.
      if (!present && !ghostPlaced && r.type === "organic") {
        api.col.append(ghostRow(c));
        ghostPlaced = true;
      }
      api.col.append(serpRow(r, c));
    });
    if (!present && !ghostPlaced) api.col.append(ghostRow(c));

    const mine = rows.filter((r) => r.mapped_key).length;
    api.note.textContent =
      `The Google results page for “${api.query}”, redrawn from what we read. ` +
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
    const row = h("div.serprow" + (isYou ? ".is-you" : ""), {
      data: { clinic: r.mapped_key || null },
    });
    row.append(h("span.serprow__pos.dot-num.dot-num--sm",
                 { text: r.position === null ? "–" : String(r.position) }));
    const main = h("div.serprow__main",
      h("div.serprow__title", { text: short(r.clinic || r.title || r.domain || "—", 68) }));
    const meta = h("div.serprow__meta");
    if (TYPE_LABEL[r.type]) meta.append(h("span.tag.tag--type", { text: TYPE_LABEL[r.type] }));
    meta.append(h("span.swatch", { style: { background: `var(--kind-${r.kind})` } }));
    meta.append(h("span", { text: KIND_LABEL[r.kind] || r.kind }));
    if (r.domain) meta.append(h("span.serprow__dom", { text: r.domain }));
    main.append(meta);
    row.append(main);
    if (isYou) row.append(h("span.pill.pill--lime", { text: "you" }));
    return row;
  }

  function ghostRow(c) {
    return h("div.serprow.serprow--ghost", {
      "aria-label": `${c ? c.display_name : "This clinic"} does not appear on this page`,
    },
      h("span.serprow__pos", { text: "—" }),
      h("div.serprow__main",
        h("div.serprow__title", { text: c ? c.display_name : "Your clinic" }),
        h("div.serprow__meta", h("span", { text: "not on this page — a patient searching this never sees you" }))));
  }

  /* ═══ P6 · The treatment plan — prescription stack ════════════════════════════
     v2 rendered flat rows with a "+N". Each card here is a nested INNER surface
     (the brightest rung) carrying a dose gauge, the action, and the projected
     RANK move — the single most persuasive number in the product, and one that
     did not exist before P2. Toggling a card recomputes the compound projection,
     which is what makes it a tool rather than a list. */
  app.register({
    id: "prescription", page: "clinic", span: 7, rows: 2, subject: true,
    title: "The treatment plan", sub: "what to fix, and what it moves",

    mount(body, ctx) {
      const proj = h("div.proj");
      const list = h("div.stack.rx");
      body.append(proj, list);
      const api = { proj, list, off: new Set() };
      drawPlan(api, ctx);
      return api;
    },
    update(api, ctx) { api.off.clear(); drawPlan(api, ctx); },
  });

  function drawPlan(api, ctx) {
    const c = ctx.subject;
    const plan = c && c.plan;
    api.list.textContent = "";
    api.proj.textContent = "";
    if (!plan) return;

    const chosen = plan.steps.filter((s2) => !api.off.has(s2.key));
    // Points are additive per step; the compound figure from the payload is the
    // authority when the whole plan is selected.
    const projected = chosen.length === plan.steps.length
      ? plan.compound.all.vis
      : Math.min(100, plan.now.vis + chosen.reduce((a, s2) => a + s2.lift, 0));
    const projRank = chosen.length === plan.steps.length ? plan.compound.all.rank
      : (chosen.length ? estimateRank(ctx, projected) : plan.now.rank);

    // Header: today and the projection on ONE shared ruler.
    //
    // The full-plan figure is a CEILING, not a forecast: close every gap and 27 of
    // 34 clinics land on exactly (100, #2), so headlining it tells this clinic
    // nothing and reads as a sales promise. It is stated below as the ceiling it
    // is. The top-two projection genuinely varies across the market (ranks 1-11)
    // and is the decision actually on the table.
    const label = chosen.length === plan.steps.length ? "with every gap closed"
      : (chosen.length ? "with what you have selected" : "with nothing selected");

    api.proj.append(
      h("div.proj__head",
        h("div.row",
          h("span.disp", { text: `#${plan.now.rank}` }),
          h("span.unit", { text: "today" }),
          h("span.proj__arrow", { text: "→", "aria-hidden": "true" }),
          h("span.disp.proj__after", { text: `#${projRank}` }),
          h("span.unit", { text: label })),
        h("div.metric__c", { text: `visibility ${plan.now.vis} → ${projected} of 100` })),
      projRuler(plan.now.vis, projected),
      h("p.caveat", {
        text: `Closing every gap tops out at #${plan.compound.all.rank} of ${c.visibility_total} — ` +
              `that is the arithmetic ceiling for any clinic in this market, not a forecast. ` +
              `Your first two fixes alone reach #${plan.compound.top2.rank}.`,
      }));

    if (!plan.steps.length) {
      api.list.append(h("div.inner", h("div.metric__c", {
        text: "Nothing material left to fix — keep reviews fresh and hold the position.",
      })));
      return;
    }

    plan.steps.forEach((step, i) => {
      const on = !api.off.has(step.key);
      const card = h("div.inner.rx__card" + (on ? "" : ".is-off"));
      card.append(h("div.rx__gauge", { "aria-hidden": "true" }, doseGauge(step.lift)));
      const mid = h("div.rx__mid",
        h("div.rx__action", { text: RX_COPY[step.key] || step.label }),
        h("div.metric__c", { text: RX_WHY[step.key] || "" }));
      card.append(mid);
      card.append(h("div.rx__move",
        h("span.disp", { text: `#${plan.now.rank} → #${step.rank_after}` }),
        h("span.metric__c", { text: `+${step.lift} points` })));
      card.append(h("button.rx__toggle", {
        type: "button", text: on ? "in the plan" : "add",
        "aria-pressed": String(on),
        "aria-label": `${on ? "Remove" : "Add"} ${RX_COPY[step.key] || step.label}`,
        onclick: () => {
          if (api.off.has(step.key)) api.off.delete(step.key); else api.off.add(step.key);
          drawPlan(api, app.context());
        },
      }));
      // The journey connector threads the cards into an ordered course.
      if (i < plan.steps.length - 1) card.append(h("i.rx__link", { "aria-hidden": "true" }));
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
    website: "Right now a patient who Googles you has nowhere of yours to land.",
    search: "Directories are capturing the patients who search for your treatments.",
    maps: "The map box is the first thing on the page for local searches.",
    reviews: "Reviews are the trust signal patients read before they call.",
    phone: "The last step before a booking should never be a dead end.",
    breadth: "You are visible for a narrow slice of what patients actually ask.",
  };

  /** Estimate the rank a projected score would earn, against the unchanged market. */
  function estimateRank(ctx, vis) {
    const others = ctx.all.filter((x) => x.key !== ctx.subject.key).map((x) => x.visibility || 0);
    return others.filter((v) => v > vis).length + 1;
  }

  function doseGauge(lift) {
    const cells = 6, lit = clamp(Math.round(lift / 5), 1, cells);
    const w = 12, cellH = 7, hgt = cells * cellH;
    const bars = [];
    for (let i = 0; i < cells; i++) {
      bars.push(s("rect", { x: 0, y: hgt - (i + 1) * cellH + 1.5, width: w, height: cellH - 3,
                            rx: 1.5, class: i < lit ? "dose dose--lit" : "dose" }));
    }
    return s("svg", { class: "viz", viewBox: `0 0 ${w} ${hgt}`, width: w, height: hgt,
                      "aria-hidden": "true" }, bars);
  }

  function projRuler(now, after) {
    const w = 320, hgt = 26, ticks = [];
    for (let i = 0; i <= 20; i++) {
      const major = i % 5 === 0;
      ticks.push(s("rect", { x: (i * (w / 20)).toFixed(1), y: hgt - (major ? 14 : 8),
                             width: 1.5, height: major ? 14 : 8, rx: .7, class: "tick" }));
    }
    const xa = (clamp(now, 0, 100) / 100) * (w - 3);
    const xb = (clamp(after, 0, 100) / 100) * (w - 3);
    return s("svg", { class: "viz proj__ruler", viewBox: `0 0 ${w} ${hgt}`,
                      preserveAspectRatio: "none", height: hgt, "aria-hidden": "true" },
      ticks,
      s("rect", { x: Math.min(xa, xb).toFixed(1), y: hgt - 4, width: Math.abs(xb - xa).toFixed(1),
                  height: 3, rx: 1.5, class: "proj__span" }),
      s("rect", { x: xa.toFixed(1), y: 0, width: 3, height: hgt, rx: 1.5, class: "proj__now" }),
      s("rect", { x: xb.toFixed(1), y: 0, width: 3, height: hgt, rx: 1.5, class: "proj__goal" }));
  }

  /* ═══ P7 · Patient voice ═════════════════════════════════════════════════════
     One dot per review actually read, with deterministic jitter. The sample size
     is printed in the panel rather than hidden: 10 reviews is a sample, not a
     trend, and the design must not imply otherwise. */
  app.register({
    id: "voice", page: "clinic", span: 5, subject: true,
    title: "Patient voice",

    mount(body, ctx) {
      const wrap = h("div.stack");
      body.append(wrap);
      const api = { wrap };
      drawVoice(api, ctx);
      return api;
    },
    update(api, ctx) { drawVoice(api, ctx); },
  });

  function drawVoice(api, ctx) {
    const c = ctx.subject;
    api.wrap.textContent = "";
    const n = c && c.nlp;
    if (!n) {
      api.wrap.append(h("div.metric__c", {
        text: "No reviews were captured for this clinic, so there is nothing to read here yet.",
      }));
      return;
    }

    const total = n.n || 0;
    const pos = Math.round((n.pos / 100) * total);
    const dots = [];
    const per = 10, cell = 14;
    for (let i = 0; i < total; i++) {
      const jx = (inst.rand(`${c.key}vx${i}`) - 0.5) * 4;
      const jy = (inst.rand(`${c.key}vy${i}`) - 0.5) * 4;
      dots.push(s("circle", {
        cx: ((i % per) * cell + cell / 2 + jx).toFixed(1),
        cy: (Math.floor(i / per) * cell + cell / 2 + jy).toFixed(1),
        r: 4.6, class: i < pos ? "vdot vdot--pos" : "vdot vdot--neg",
      }));
    }
    const rows = Math.ceil(total / per);
    api.wrap.append(s("svg", {
      class: "viz voice", viewBox: `0 0 ${per * cell} ${rows * cell}`,
      height: rows * cell * 1.5, preserveAspectRatio: "xMinYMid meet",
      role: "img", "aria-label": `${pos} of ${total} reviews read were positive`,
    }, dots));

    api.wrap.append(h("div.metric__c", {
      text: `${pos} of ${total} reviews read were positive · ${pct((n.referral || 0), 0)} mention being referred`,
    }));

    if ((n.themes || []).length) {
      api.wrap.append(h("div.row", h("span.metric__c", { text: "Praised" }),
        ...n.themes.map((t) => h("span.pill", { text: t }))));
    }
    if ((n.pains || []).length) {
      api.wrap.append(h("div.row", h("span.metric__c", { text: "Watch-outs" }),
        ...n.pains.map((t) => h("span.pill.pill--warn", { text: t }))));
    }
    api.wrap.append(h("p.caveat", {
      text: `${total} reviews read — a sample of what patients say, not a trend over time.`,
    }));
  }

  /* ═══ P8 · Where you sit ═════════════════════════════════════════════════════
     The only geography in the product. Not a slippy map — no tiles, no network,
     ~0 KB: 34 dots in normalised lat/lng with distance rings from the city core.
     This also replaces v2's brittle 13-name address-substring "area" facet. */
  app.register({
    id: "constellation", page: "clinic", span: 5, subject: true,
    title: "Where you sit", sub: "distance from the city core",

    mount(body, ctx) {
      const host = h("div.map-host");
      const note = h("p.caveat");
      body.append(host, note);
      const api = { host, note };
      drawMap(api, ctx);
      host.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "constellation");
      });
      host.addEventListener("pointerleave", () => bus.hover(null, "constellation"));
      host.addEventListener("click", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        if (n && store.select(n.dataset.clinic)) bus.emit("select", { key: n.dataset.clinic });
      });
      return api;
    },
    update(api, ctx) { drawMap(api, ctx); },
    highlight(api, key) { inst.hilite(api.host, key); },
  });

  function drawMap(api, ctx) {
    const pts = ctx.all.filter((c) => c.lat !== null && c.lng !== null);
    if (!pts.length) { api.host.textContent = ""; return; }
    const size = 300, pad = 26;
    const lats = pts.map((c) => c.lat), lngs = pts.map((c) => c.lng);
    const lat0 = Math.min(...lats), lat1 = Math.max(...lats);
    const lng0 = Math.min(...lngs), lng1 = Math.max(...lngs);
    const X = (lng) => pad + ((lng - lng0) / ((lng1 - lng0) || 1)) * (size - pad * 2);
    // Latitude increases northward but SVG y increases downward, so invert.
    const Y = (lat) => size - pad - ((lat - lat0) / ((lat1 - lat0) || 1)) * (size - pad * 2);

    const core = [16.3067, 80.4365];
    const cx = X(core[1]), cy = Y(core[0]);
    // 1 km in degrees of longitude at this latitude -> px
    const kmPx = Math.abs(X(core[1] + 1 / 106.6) - cx);

    const kids = [];
    for (const km of [1, 2]) {
      kids.push(s("circle", { cx, cy, r: (kmPx * km).toFixed(1), class: "map-ring", fill: "none" }));
      kids.push(s("text", { x: (cx + kmPx * km + 3).toFixed(1), y: (cy - 3).toFixed(1),
                            class: "map-km" }, `${km} km`));
    }
    kids.push(s("circle", { cx, cy, r: 4, class: "map-core" }));

    const subject = ctx.subject;
    for (const c of pts) {
      const inView = ctx.keys.has(c.key);
      const isYou = subject && c.key === subject.key;
      kids.push(s("circle", {
        cx: X(c.lng).toFixed(1), cy: Y(c.lat).toFixed(1),
        r: isYou ? 7 : 5,
        class: `map-dot map-dot--${store.bandOf(c.visibility)}` + (isYou ? " is-you" : "") +
               (inView ? "" : " is-out"),
        data: { clinic: c.key },
      }, s("title", {}, `${c.display_name} · visibility ${c.visibility} · ${c.km_core} km from the core`)));
    }

    api.host.textContent = "";
    api.host.append(s("svg", { class: "viz map", viewBox: `0 0 ${size} ${size}`,
                               role: "img", "aria-label": "Clinic locations around the Guntur city core" }, kids));
    api.note.textContent = subject && subject.km_core !== null
      ? `You are ${subject.km_core} km from the city core. Dot colour is where each clinic stands online.`
      : "Dot colour is where each clinic stands online.";
  }
})(window.DI);
