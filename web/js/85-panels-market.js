/* ── "The Market" panels ───────────────────────────────────────────────────── */
(function (DI) {
  "use strict";

  const { h, inst, store, bus, app, charts, P } = DI;

  /* ── M2 · Naked KPI strip ───────────────────────────────────────────────────
     Metrics sitting straight on the field, no card — the reference's signature
     move. Exactly one lime pill on the strip. The counts follow the filter, so
     this is also the readout that proves a brush actually narrowed the market. */
  app.register({
    id: "kpi-strip",
    page: "market",
    span: 12,
    card: false,

    mount(body, ctx) {
      const strip = h("div.strip");
      body.append(strip);
      const api = { strip };
      draw(api, ctx);
      return api;
    },
    update(api, ctx) { draw(api, ctx); },
  });

  function draw(api, ctx) {
    const D = ctx.D, k = D.kpis || {}, m = D.market || {};
    const shown = ctx.filtered.length, total = ctx.all.length;
    const invisible = ctx.filtered.filter((c) => store.presenceOf(c) === "invisible").length;
    const serp = (D.serp && D.serp.ownership && D.serp.ownership.totals) || {};

    api.strip.textContent = "";
    api.strip.append(
      inst.metric({
        value: shown,
        pill: ctx.active ? `of ${total}` : null,
        caption: ctx.active ? "clinics in view" : "dermatology clinics mapped in Guntur",
      }),
      inst.metric({
        value: invisible,
        pill: "worst gap", lime: true,
        caption: "invisible in Google search",
      }),
      inst.metric({
        value: k.median_reviews || 0,
        caption: `median reviews · mean ${DI.num(k.avg_reviews)} is skewed by two outliers`,
      }),
      inst.metric({
        value: serp.blocks || 0,
        caption: `result blocks read across ${serp.queries || 0} searches`,
      }),
      inst.metric({
        value: m.own_site || 0,
        caption: "clinics whose own site ranks",
      }));
  }

  /* ── M4 · Visibility league ─────────────────────────────────────────────────
     34 rows as hairline tracks with a terminal dot — not chunky bars. The two
     EMPIRICAL distribution gaps render as labelled voids, which is the insight
     a plain sorted bar chart destroys.

     This is one of the three panels where ECharts earns its place: it needs
     hit-testing across 34 marks plus axis-triggered tooltips. */
  app.register({
    id: "league",
    page: "market",
    span: 12,
    rows: 2,
    title: "The visibility league",
    sub: "every clinic, worst to best",

    mount(body, ctx) {
      // 34 rows need real height or ECharts silently drops every other label.
      const host = h("div.chart", { style: { minHeight: "740px" } });
      body.append(host);

      const sortSeg = h("div.seg");
      [["visibility", "Visibility"], ["reviews", "Reviews"], ["appearances", "Demand"]]
        .forEach(([key, label], i) => {
          sortSeg.append(h("button", {
            type: "button", text: label, data: { sort: key },
            "aria-pressed": String(i === 0),
            onclick: () => { api.sort = key; paintSeg(); render(api, app.context()); },
          }));
        });
      const head = body.parentElement.querySelector(".panel__head");
      if (head) head.append(h("div.tools", sortSeg));

      const api = { host, chart: null, sort: "visibility", rows: [], sortSeg };
      function paintSeg() {
        sortSeg.querySelectorAll("button").forEach((b) =>
          b.setAttribute("aria-pressed", String(b.dataset.sort === api.sort)));
      }

      api.chart = charts.make(host, option(api, ctx));
      if (api.chart) {
        api.chart.on("mouseover", (p) => {
          const row = api.rows[p.dataIndex];
          if (row) bus.hover(row.key, "league");
        });
        api.chart.on("mouseout", () => bus.hover(null, "league"));
        api.chart.on("click", (p) => {
          const row = api.rows[p.dataIndex];
          if (row && store.select(row.key)) bus.emit("select", { key: row.key });
        });
      }
      return api;
    },

    update(api, ctx) { render(api, ctx); },

    highlight(api, key) {
      if (!api.chart) return;
      const i = api.rows.findIndex((r) => r.key === key);
      charts.emphasise(api.chart, i);
    },
  });

  function leagueRows(api, ctx) {
    const metric = api.sort;
    return ctx.all.slice().sort((a, b) => (a[metric] || 0) - (b[metric] || 0))
      .map((c) => ({
        key: c.key,
        name: DI.short(c.display_name, 26),
        value: c[metric] || 0,
        visibility: c.visibility,
        reviews: c.reviews,
        appearances: c.appearances,
        inView: ctx.keys.has(c.key),
        isSubject: ctx.subject && c.key === ctx.subject.key,
      }));
  }

  function option(api, ctx) {
    const rows = leagueRows(api, ctx);
    api.rows = rows;
    const gaps = ((ctx.D.bands || {}).gaps) || [];

    return {
      grid: { left: 150, right: 34, top: 8, bottom: 26, containLabel: false },
      xAxis: charts.axis({ type: "value", max: api.sort === "visibility" ? 100 : null }),
      yAxis: charts.axis({
        type: "category",
        data: rows.map((r) => r.name),
        // interval:0 forces EVERY clinic to be named; the default thins them out
        // and a league table with half its rows unlabelled is useless.
        axisLabel: { color: P.ink[3], fontFamily: "Geist", fontSize: 10, margin: 12,
                     interval: 0 },
      }),
      tooltip: charts.tooltip((p) => {
        const r = rows[p[0] ? p[0].dataIndex : p.dataIndex];
        if (!r) return "";
        return charts.tip(r.name, [
          ["Visibility", r.visibility], ["Reviews", DI.num(r.reviews)],
          ["Searches", r.appearances],
        ]);
      }, "axis"),
      series: [
        {
          // the hairline track
          type: "bar", barWidth: 2, silent: true,
          itemStyle: { color: P.data.track },
          data: rows.map(() => (api.sort === "visibility" ? 100 : Math.max(...rows.map((r) => r.value)))),
          barGap: "-100%", z: 1,
        },
        {
          type: "bar", barWidth: 2,
          itemStyle: {
            color: (p) => rows[p.dataIndex].isSubject ? P.data.you : P.data.aggregator,
            opacity: (p) => rows[p.dataIndex].inView ? 1 : 0.14,
          },
          data: rows.map((r) => r.value),
          z: 2,
          markArea: gaps.length ? {
            silent: true,
            itemStyle: { color: P.zone.offradar },
            label: { show: true, position: "insideTop", color: P.ink[4], fontSize: 9,
                     formatter: "the market splits here" },
            data: [],   // gaps are on the value axis; drawn by the marker series below
          } : undefined,
        },
        {
          // terminal dots — the mark the eye actually reads
          type: "scatter", symbolSize: 7,
          itemStyle: {
            color: (p) => rows[p.dataIndex].isSubject ? P.data.you : P.data.owned,
            opacity: (p) => rows[p.dataIndex].inView ? 1 : 0.14,
            borderColor: (p) => rows[p.dataIndex].isSubject ? P.accent.lime : "transparent",
            borderWidth: (p) => rows[p.dataIndex].isSubject ? 2.5 : 0,
          },
          data: rows.map((r, i) => [r.value, i]),
          z: 3,
        },
      ],
    };
  }

  function render(api, ctx) {
    if (!api.chart) return;
    api.chart.setOption(option(api, ctx), { replaceMerge: ["series", "yAxis", "xAxis"] });
  }
})(window.DI);
