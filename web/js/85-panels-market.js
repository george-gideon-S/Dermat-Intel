/* ── "The Market" panels ──────────────────────────────────────────────────────
     M1 jewels 7      M2 strip 5
     M3 opportunity 8×2   M4 league 4×2
     M5 who owns the SERP 12
     M6 ad shelf 5    M7 owned vs borrowed 7
     M8 funnel 4      M9 intents 4    M10 map 4
     M11 all clinics 12                                                        */
(function (DI) {
  "use strict";

  const { h, s, inst, store, bus, app, charts, P, num, short, clamp, median } = DI;

  /* ═══ M1 · Market twin jewels ════════════════════════════════════════════════ */
  app.register({
    id: "market-jewels", page: "market", span: 7, card: false,
    mount(body, ctx) {
      const wrap = h("div.jewel-pair");
      body.append(wrap);
      const api = { wrap };
      drawMarketJewels(api, ctx);
      return api;
    },
    update(api, ctx) { drawMarketJewels(api, ctx); },
  });

  function drawMarketJewels(api, ctx) {
    const rows = ctx.filtered.length ? ctx.filtered : ctx.all;
    const invisible = rows.filter((c) => store.presenceOf(c) === "invisible").length;
    const own = rows.filter((c) => store.presenceOf(c) === "own").length;
    const total = rows.length;

    api.wrap.textContent = "";
    api.wrap.append(
      inst.jewel({
        family: "caution", label: "Invisible in Google search", value: invisible,
        sub: `of ${total} clinics · ${Math.round((invisible / (total || 1)) * 100)}% of the market`,
        viz: inst.dotColumn(rows.map((c) => store.presenceOf(c) === "invisible" ? 9 : 2), { height: 40 }),
        ariaLabel: `${invisible} of ${total} clinics are invisible in Google search.`,
      }),
      inst.jewel({
        family: "clear", label: "Own site ranks", value: own,
        sub: `of ${total} clinics hold their own ground`,
        viz: inst.tickRuler(total, total ? (own - 0.5) / total : 0, { height: 26 }),
        ariaLabel: `${own} of ${total} clinics rank with their own website.`,
      }));
  }

  /* ═══ M2 · Naked KPI strip ═══════════════════════════════════════════════════
     Metrics straight on the field. Counts follow the filter, so this is also the
     readout that proves a brush narrowed the market. */
  app.register({
    id: "kpi-strip", page: "market", span: 5, card: false,
    mount(body, ctx) {
      const strip = h("div.strip.strip--tight");
      body.append(strip);
      const api = { strip };
      drawStrip(api, ctx);
      return api;
    },
    update(api, ctx) { drawStrip(api, ctx); },
  });

  function drawStrip(api, ctx) {
    const D = ctx.D, k = D.kpis || {};
    const serp = ((D.serp || {}).ownership || {}).totals || {};
    api.strip.textContent = "";
    api.strip.append(
      inst.metric({
        value: ctx.filtered.length,
        pill: ctx.active ? `of ${ctx.all.length}` : null, lime: ctx.active,
        caption: ctx.active ? "clinics in view" : "clinics mapped in Guntur",
      }),
      inst.metric({
        value: k.median_reviews || 0,
        // Derived, and true: "pulled up by two outliers" was not — removing the
        // top two still leaves the mean 43% above the median, and ten clinics
        // sit above it.
        caption: `median reviews — ${ctx.all.filter((c) => (c.reviews || 0) < (k.avg_reviews || 0)).length} ` +
                 `of ${ctx.all.length} clinics sit below the mean of ${num(k.avg_reviews)}`,
      }),
      inst.metric({
        value: serp.blocks || 0,
        caption: `results read across ${serp.queries || 0} searches`,
      }),
      inst.metric({
        value: `${k.queries || 0}`,
        caption: `patient searches mapped · ${serp.queries || 0} read on the web, 50 on Maps`,
      }));
  }

  /* ═══ M3 · The opportunity map ═══════════════════════════════════════════════
     The flagship cross-filter surface: hover -> bus, click -> select, and a
     rectangle BRUSH that filters every other panel on the page.

     Zones are cut on the two axes actually plotted (demand x visibility). The
     tested analytics.quadrant_frame cuts on rating instead, and rating is a known
     trap here — 28 of 34 clinics sit between 4.8 and 5.0 — so using it would draw
     zone plates that contradict the picture. */
  app.register({
    id: "opportunity", page: "market", span: 8, rows: 2,
    title: "The opportunity map", sub: "demand against visibility",

    mount(body, ctx) {
      const host = h("div.chart", { style: { minHeight: "440px" } });
      const legend = h("div.legend");
      const note = h("p.caveat", {
        text: "Drag a box to filter every panel on this page. Bubble size is review count.",
      });
      body.append(host, legend, note);

      const api = { host, legend, chart: null, rows: [], off: new Set() };
      api.chart = charts.make(host, mapOption(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          if (p.seriesIndex !== 1) return;
          const r = api.rows[p.dataIndex];
          if (r) bus.hover(r.key, "opportunity");
        });
        api.chart.on("mouseout", () => bus.hover(null, "opportunity"));
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
                             color: "rgba(35,35,35,0.04)" } },
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
            borderColor: r.isSubject ? P.accent.lime : "transparent",
            borderWidth: r.isSubject ? 3 : 0,
          },
        })),
      }],
    };
  }

  /* ═══ M4 · Visibility league ═════════════════════════════════════════════════
     Hairline tracks with a terminal dot, not chunky bars. The two EMPIRICAL
     distribution gaps are drawn as labelled voids — the insight a plain sorted
     bar chart destroys. */
  app.register({
    id: "league", page: "market", span: 4, rows: 2,
    title: "The visibility league",

    mount(body, ctx) {
      const host = h("div.chart", { style: { minHeight: "760px" } });
      body.append(host);
      const seg = h("div.seg");
      [["visibility", "Visibility"], ["reviews", "Reviews"], ["appearances", "Demand"]]
        .forEach(([key, label], i) => seg.append(h("button", {
          type: "button", text: label, data: { sort: key },
          "aria-pressed": String(i === 0),
          onclick: () => {
            api.sort = key;
            seg.querySelectorAll("button").forEach((b) =>
              b.setAttribute("aria-pressed", String(b.dataset.sort === key)));
            render(api, app.context());
          },
        })));
      const head = body.parentElement.querySelector(".panel__head");
      if (head) head.append(h("div.tools", seg));

      const api = { host, chart: null, sort: "visibility", rows: [] };
      api.chart = charts.make(host, leagueOption(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          const r = api.rows[p.dataIndex];
          if (r) bus.hover(r.key, "league");
        });
        api.chart.on("mouseout", () => bus.hover(null, "league"));
        api.chart.on("click", (p) => {
          const r = api.rows[p.dataIndex];
          if (r && store.select(r.key)) bus.emit("select", { key: r.key });
        });
      }
      return api;
    },
    update(api, ctx) { render(api, ctx); },
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
        inView: ctx.keys.has(c.key),
        isSubject: ctx.subject && c.key === ctx.subject.key,
      }));
    api.rows = rows;
    const maxV = Math.max(...rows.map((r) => r.value), 1);
    const axisMax = metric === "visibility" ? 100 : maxV;
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
            itemStyle: { color: r.isSubject ? P.data.you : P.data.aggregator,
                         opacity: r.inView ? 1 : 0.12 },
          })),
          // The empirical voids, drawn where the market actually splits.
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
                         opacity: r.inView ? 1 : 0.12,
                         borderColor: r.isSubject ? P.accent.lime : "transparent",
                         borderWidth: r.isSubject ? 2.5 : 0 },
          })) },
      ],
    };
  }

  function render(api, ctx) {
    if (api.chart) api.chart.setOption(leagueOption(api, ctx),
                                       { replaceMerge: ["series", "yAxis", "xAxis"] });
  }

  /* ═══ M5 · Who owns the Guntur SERP ══════════════════════════════════════════
     The flagship new panel — 1122 result blocks, entirely unbuilt before now.
     A domain × block-type matrix where every cell is a dot column, so it reads as
     an instrument rack rather than a heatmap. The share bar on the right carries
     the whole sales argument. */
  app.register({
    id: "serp-ownership", page: "market", span: 12,
    title: "Who owns the Guntur results", sub: "every result block we read, by domain",

    mount(body, ctx) {
      const wrap = h("div.own");
      body.append(wrap);
      const api = { wrap, sort: "blocks" };
      drawOwnership(api, ctx);
      return api;
    },
    update(api, ctx) { drawOwnership(api, ctx); },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  const TYPES = [
    ["sponsored_top", "Ads (top)"], ["places", "Map pack"],
    ["sponsored_mid", "Ads (mid)"], ["organic", "Organic"], ["ai_overview", "AI answer"],
  ];

  function drawOwnership(api, ctx) {
    const own = (ctx.D.serp || {}).ownership;
    if (!own) return;
    const rows = own.domains.slice(0, 16);
    const t = own.totals;

    api.wrap.textContent = "";

    // The argument, stated once, in words and one bar.
    const localOrganic = (own.local_share.organic || {}).local || 0;
    const otherOrganic = (own.local_share.organic || {}).other || 0;
    api.wrap.append(h("div.own__lead",
      h("div.row",
        inst.metric({ value: t.unmapped, pill: "of " + num(t.blocks), lime: true,
                      caption: "result blocks belong to nobody in Guntur" }),
        inst.metric({ value: otherOrganic,
                      caption: `of ${otherOrganic + localOrganic} organic results are held by directories, chains and out-of-town sites` })),
      shareBar(own)));

    const grid = h("div.own__grid");
    grid.append(h("div.own__h"), ...TYPES.map(([, label]) =>
      h("div.own__h.own__h--num", { text: label })), h("div.own__h.own__h--num", { text: "Blocks" }));

    const maxCell = Math.max(1, ...rows.flatMap((d) => TYPES.map(([tk]) => d.by_type[tk] || 0)));
    for (const d of rows) {
      const label = h("button.own__row", {
        type: "button", data: { clinic: d.clinic_key || null },
        title: d.domain_known ? d.domain
          : `${d.domain} — ${d.clinics} clinics whose domain we could not read`,
        onclick: () => openDomainDrawer(d, ctx),
      },
        h("span.swatch", { style: { background: `var(--kind-${d.kind})` } }),
        h("span.own__dom", { text: d.domain_known ? d.domain : `${d.domain} · ${d.clinics} clinics` }));
      grid.append(label);
      for (const [tk] of TYPES) {
        grid.append(h("div.own__cell", cellDots(d.by_type[tk] || 0, maxCell)));
      }
      grid.append(h("div.own__n.dot-num.dot-num--sm", { text: String(d.blocks) }));
    }
    api.wrap.append(grid);
    api.wrap.append(h("p.caveat", {
      text: `Top ${rows.length} domains of ${own.domains.length}. A row marked with a clinic count is a ` +
            `bucket of clinic sites whose domain the extraction never captured.`,
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

  function shareBar(own) {
    const t = own.totals;
    const local = t.mapped, other = t.unmapped;
    return h("div.own__share", { "aria-hidden": "true" },
      h("i", { style: { width: `${(local / t.blocks) * 100}%`,
                        background: "var(--data-owned)" }, title: `${local} local` }),
      h("i", { style: { width: `${(other / t.blocks) * 100}%`,
                        background: "var(--data-outside)" }, title: `${other} not local` }));
  }

  function openDomainDrawer(d, ctx) {
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

  /* ═══ M6 · The ad shelf ══════════════════════════════════════════════════════
     31 of 34 clinics have never bought a slot. The emptiness IS the chart. */
  app.register({
    id: "ad-shelf", page: "market", span: 5,
    title: "Who is paying for the page", sub: "Google ads bought, by clinic",

    mount(body, ctx) {
      const wrap = h("div.shelf");
      const note = h("p.caveat");
      body.append(wrap, note);
      const api = { wrap, note };
      drawShelf(api, ctx);
      wrap.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "ad-shelf");
      });
      wrap.addEventListener("pointerleave", () => bus.hover(null, "ad-shelf"));
      wrap.addEventListener("click", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        if (n && store.select(n.dataset.clinic)) bus.emit("select", { key: n.dataset.clinic });
      });
      return api;
    },
    update(api, ctx) { drawShelf(api, ctx); },
    highlight(api, key) { inst.hilite(api.wrap, key); },
  });

  function drawShelf(api, ctx) {
    const rows = ctx.all.slice().sort((a, b) => (b.sponsored || 0) - (a.sponsored || 0));
    const maxAd = Math.max(...rows.map((c) => c.sponsored || 0), 1);
    const buyers = rows.filter((c) => (c.sponsored || 0) > 0).length;
    const serpQ = (((ctx.D.serp || {}).ownership || {}).totals || {}).queries || 78;

    api.wrap.textContent = "";
    for (const c of rows) {
      const n = c.sponsored || 0;
      const row = h("div.shelf__row", {
        data: { clinic: c.key },
        title: `${c.display_name} · ${n} of ${serpQ} searches`,
      },
        h("span.shelf__name", { text: short(c.display_name, 24) }),
        h("span.shelf__fil", h("i", { style: { width: `${(n / maxAd) * 100}%` } })),
        h("span.shelf__n", { text: n ? String(n) : "" }));
      if (!n) row.classList.add("is-empty");
      if (ctx.subject && c.key === ctx.subject.key) row.classList.add("is-you");
      api.wrap.append(row);
    }
    // Everything here is derived. The previous copy hard-coded "the three that do
    // are chains" in the same sentence as a computed count of seven, above a list
    // of seven.
    const heavy = rows.filter((c) => (c.sponsored || 0) >= 10);
    api.note.textContent =
      `${rows.length - buyers} of ${rows.length} clinics have never bought a single ad slot. ` +
      (heavy.length
        ? `${heavy.length} of the ${buyers} that do (${heavy.map((c) => short(c.display_name, 18)).join(", ")}) ` +
          `bid on ten or more searches and take the top of the page before anyone scrolls.`
        : `The ${buyers} that do bid on only a handful of searches each.`);
  }

  /* ═══ M7 · Owned vs borrowed ═════════════════════════════════════════════════
     A centre-spine dumbbell across ALL 34 clinics (v2 truncated to 16). Clinics
     with nothing at all render as a single hollow dot on the spine — honest,
     rather than hidden by the truncation. */
  app.register({
    id: "owned-borrowed", page: "market", span: 7,
    title: "Own ground vs borrowed ground", sub: "own site left, directories right",

    mount(body, ctx) {
      const host = h("div.chart", { style: { minHeight: "560px" } });
      body.append(host);
      const api = { host, chart: null, rows: [] };
      api.chart = charts.make(host, obOption(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          const r = api.rows[p.dataIndex];
          if (r) bus.hover(r.key, "owned-borrowed");
        });
        api.chart.on("mouseout", () => bus.hover(null, "owned-borrowed"));
        api.chart.on("click", (p) => {
          const r = api.rows[p.dataIndex];
          if (r && store.select(r.key)) bus.emit("select", { key: r.key });
        });
      }
      return api;
    },
    update(api, ctx) {
      if (api.chart) api.chart.setOption(obOption(api, ctx), { replaceMerge: ["series", "yAxis"] });
    },
    highlight(api, key) {
      charts.emphasise(api.chart, api.rows.findIndex((r) => r.key === key));
    },
  });

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
            itemStyle: { color: "transparent", borderColor: P.data.absent, borderWidth: 1.4 },
          })) },
      ],
    };
  }

  /* ═══ M8 · The presence funnel ═══════════════════════════════════════════════
     analytics.presence_funnel has been tested since day one and never surfaced.
     Five tick-ruler steps, not a trapezoid. */
  app.register({
    id: "funnel", page: "market", span: 4,
    title: "How far the market gets", sub: "clinics surviving each step",

    mount(body, ctx) {
      const wrap = h("div.stack.funnel");
      body.append(wrap);
      const api = { wrap };
      drawFunnel(api, ctx);
      return api;
    },
    update(api, ctx) { drawFunnel(api, ctx); },
  });

  function drawFunnel(api, ctx) {
    const steps = ctx.D.funnel || [];
    if (!steps.length) return;
    const top = steps[0].count || 1;
    api.wrap.textContent = "";
    for (const st of steps) {
      api.wrap.append(h("div.funnel__row",
        h("span.funnel__k", { text: st.step }),
        h("span.funnel__bar", inst.tickRuler(24, null, { height: 16 }),
          h("i", { style: { width: `${(st.count / top) * 100}%` } })),
        h("span.dot-num.dot-num--sm.funnel__n", { text: String(st.count) })));
    }
  }

  /* ═══ M9 · What patients search for ══════════════════════════════════════════
     Honestly labelled: Condition-Based is 52 of 80 queries, and a category with
     no queries at all is shown as an explicit zero row rather than left out. */
  app.register({
    id: "categories", page: "market", span: 4,
    title: "What patients search for", sub: "by intent",

    mount(body, ctx) {
      const wrap = h("div.stack.cats");
      const note = h("p.caveat");
      body.append(wrap, note);
      const api = { wrap, note };
      drawCats(api, ctx);
      return api;
    },
    update(api, ctx) { drawCats(api, ctx); },
  });

  function drawCats(api, ctx) {
    const cats = (ctx.D.categories || []).slice()
      .sort((a, b) => (b.count || 0) - (a.count || 0));
    const total = cats.reduce((a, c) => a + (c.count || 0), 0) || 1;
    const maxC = Math.max(...cats.map((c) => c.count || 0), 1);
    const active = store.state.filter.category;

    api.wrap.textContent = "";
    for (const c of cats) {
      const on = active.has(c.category);
      api.wrap.append(h("button.cats__row" + (on ? ".is-on" : ""), {
        type: "button", "aria-pressed": String(on),
        onclick: () => { store.toggleFacet("category", c.category); bus.emit("filter", {}); },
      },
        h("span.cats__k", { text: c.category }),
        h("span.cats__bar", h("i", { style: { width: `${(c.count / maxC) * 100}%` } })),
        h("span.cats__n", { text: `${c.count}` })));
    }
    const top = cats[0];
    api.note.textContent = top
      ? `${top.category} is ${top.count} of ${total} searches — ${Math.round((top.count / total) * 100)}% of everything patients ask. Click a row to filter the page.`
      : "";
  }

  /* ═══ M10 · The market map ═══════════════════════════════════════════════════ */
  app.register({
    id: "market-map", page: "market", span: 4,
    title: "Where the market sits", sub: "colour is online standing",

    mount(body, ctx) {
      const host = h("div.map-host");
      body.append(host);
      const api = { host };
      drawMarketMap(api, ctx);
      host.addEventListener("pointermove", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        bus.hover(n ? n.dataset.clinic : null, "market-map");
      });
      host.addEventListener("pointerleave", () => bus.hover(null, "market-map"));
      host.addEventListener("click", (e) => {
        const n = e.target.closest && e.target.closest("[data-clinic]");
        if (n && store.select(n.dataset.clinic)) bus.emit("select", { key: n.dataset.clinic });
      });
      return api;
    },
    update(api, ctx) { drawMarketMap(api, ctx); },
    highlight(api, key) { inst.hilite(api.host, key); },
  });

  function drawMarketMap(api, ctx) {
    const pts = ctx.all.filter((c) => c.lat !== null && c.lng !== null);
    if (!pts.length) return;
    const size = 280, pad = 24;
    const lats = pts.map((c) => c.lat), lngs = pts.map((c) => c.lng);
    const la0 = Math.min(...lats), la1 = Math.max(...lats);
    const ln0 = Math.min(...lngs), ln1 = Math.max(...lngs);
    const X = (lng) => pad + ((lng - ln0) / ((ln1 - ln0) || 1)) * (size - pad * 2);
    const Y = (lat) => size - pad - ((lat - la0) / ((la1 - la0) || 1)) * (size - pad * 2);
    const cx = X(80.4365), cy = Y(16.3067);
    const kmPx = Math.abs(X(80.4365 + 1 / 106.6) - cx);

    const kids = [];
    for (const km of [1, 2]) {
      kids.push(s("circle", { cx, cy, r: (kmPx * km).toFixed(1), class: "map-ring", fill: "none" }));
    }
    kids.push(s("circle", { cx, cy, r: 3.5, class: "map-core" }));
    for (const c of pts) {
      kids.push(s("circle", {
        cx: X(c.lng).toFixed(1), cy: Y(c.lat).toFixed(1),
        r: ctx.subject && c.key === ctx.subject.key ? 7 : 5,
        class: `map-dot map-dot--${store.bandOf(c.visibility)}` +
               (ctx.subject && c.key === ctx.subject.key ? " is-you" : "") +
               (ctx.keys.has(c.key) ? "" : " is-out"),
        data: { clinic: c.key },
      }, s("title", {}, `${c.display_name} · visibility ${c.visibility}`)));
    }
    api.host.textContent = "";
    api.host.append(s("svg", { class: "viz map", viewBox: `0 0 ${size} ${size}`,
                               role: "img", "aria-label": "Clinics around the Guntur core" }, kids));
  }

  /* ═══ M11 · All clinics ══════════════════════════════════════════════════════
     No zebra stripes, no vertical rules, no bordered grid. */
  const COLS = [
    { key: "display_name", label: "Clinic", type: "text" },
    { key: "visibility", label: "Visibility", type: "track" },
    { key: "visibility_rank", label: "Rank", type: "num" },
    { key: "maps_score", label: "Maps gap", type: "num" },
    { key: "web_score", label: "Web gap", type: "num" },
    { key: "pos_avg", label: "Avg pos", type: "dec" },
    { key: "reviews", label: "Reviews", type: "num" },
    { key: "appearances", label: "Searches", type: "num" },
    { key: "sponsored", label: "Ads", type: "num" },
  ];

  app.register({
    id: "all-clinics", page: "market", span: 12,
    title: "Every clinic", sub: "click a row to open its report",

    mount(body, ctx) {
      const wrap = h("div.tbl-wrap");
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
    for (const c of rows) {
      const isYou = ctx.subject && c.key === ctx.subject.key;
      const row = h("tr" + (isYou ? ".is-you" : ""), {
        data: { clinic: c.key },
        onclick: () => { if (store.select(c.key)) { bus.emit("select", { key: c.key }); app.go("clinic"); } },
        onpointerenter: () => bus.hover(c.key, "table"),
        onpointerleave: () => bus.hover(null, "table"),
      });
      for (const col of COLS) {
        const v = c[col.key];
        if (col.type === "text") {
          row.append(h("td.tbl__name", { text: short(v, 34), title: c.name }));
        } else if (col.type === "track") {
          row.append(h("td.is-num",
            h("span.tbl__track", h("i", { style: { width: `${clamp(v || 0, 0, 100)}%` } })),
            h("span.tbl__v", { text: String(v) })));
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
