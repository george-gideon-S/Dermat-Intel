/* ── Chart factory ────────────────────────────────────────────────────────────
   ECharts earns its place on exactly three panels — the ones that need brush,
   dataZoom and hit-testing across 34+ marks. Everything else is hand-authored
   SVG in 60-instruments.js, which is why the dashboard does not read as "default
   ECharts". The shared base option below is what removes the remaining tells:
   monochrome axis furniture, no built-in legend, and a Float-pill tooltip. */
(function (DI) {
  "use strict";

  const P = DI.P;
  const charts = [];

  const DUR = DI.reduced() ? 0 : 420;

  /** Axis furniture is monochrome and quiet: the data carries all the colour. */
  function axis(extra) {
    return Object.assign({
      axisLine: { lineStyle: { color: P.data.gridline } },
      axisTick: { show: false },
      axisLabel: { color: P.ink[4], fontFamily: "Geist", fontSize: 10 },
      splitLine: { show: false },
      nameTextStyle: { color: P.ink[4], fontSize: 10 },
    }, extra || {});
  }

  /** The tooltip box is painted transparent; .di-tip in CSS is the real surface,
   *  so the pill matches the glass ladder instead of ECharts' default card. */
  const tooltip = (formatter, trigger) => ({
    trigger: trigger || "item",
    backgroundColor: "transparent",
    borderWidth: 0,
    padding: 0,
    className: "di-tip",
    appendToBody: true,
    textStyle: { color: P.ink[1], fontFamily: "Geist", fontSize: 13 },
    formatter,
  });

  /** Tooltip body builder — the ONLY place that emits an HTML string, so every
   *  interpolation goes through esc(). */
  function tip(title, rows) {
    const body = rows.filter(Boolean)
      .map(([k, v]) => `<span class="r"><span>${DI.esc(k)}</span><b>${DI.esc(v)}</b></span>`)
      .join("");
    return `<span class="t">${DI.esc(title)}</span>${body}`;
  }

  const base = {
    animationDuration: DUR,
    animationDurationUpdate: DI.reduced() ? 0 : 260,
    animationEasing: "cubicOut",
    animation: DUR > 0,
    textStyle: { fontFamily: "Geist" },
  };

  /**
   * Create a chart on `host`. Returns { chart, setOption, on } or null when
   * ECharts is unavailable (the app must still render its SVG instruments).
   */
  function make(host, option) {
    if (!host || !window.echarts) return null;
    const chart = window.echarts.init(host, null, { useDirtyRect: true });
    chart.setOption(Object.assign({}, base, option));
    charts.push(chart);
    return chart;
  }

  /** Resize every live chart. Called on window resize and on page reveal —
   *  a chart initialised inside a [hidden] section measures 0 and must be told. */
  const resizeAll = DI.coalesce(() => {
    for (const c of charts) {
      try { c.resize(); } catch (_) { /* disposed */ }
    }
  });

  /** Highlight without re-rendering: dispatchAction only, never setOption. */
  function emphasise(chart, dataIndex, seriesIndex) {
    if (!chart) return;
    chart.dispatchAction({ type: "downplay" });
    if (dataIndex !== null && dataIndex !== undefined && dataIndex >= 0) {
      const action = { type: "highlight", dataIndex };
      if (seriesIndex !== undefined) action.seriesIndex = seriesIndex;
      chart.dispatchAction(action);
    }
  }

  window.addEventListener("resize", resizeAll);

  DI.charts = { make, axis, tooltip, tip, resizeAll, emphasise, all: charts, DUR };
})(window.DI);
