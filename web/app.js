/* Derma Intel — front-end render + charts. Reads window.__DATA__ (inlined by build_web.py). */
(function () {
  "use strict";
  const D = window.__DATA__ || {};
  const app = document.getElementById("app");

  // ---- design tokens mirrored from CSS (for ECharts) ----
  const C = {
    ink: "#16150F", ink2: "#57554B", ink3: "#908E82",
    line: "#E7E5DC", line2: "#F0EFE8", surface: "#FFFFFF",
    accent: "#0F766E", clay: "#B0542C",
    opp: { Low: "#D9CDB4", Medium: "#D8B36A", High: "#C8843F", Critical: "#A6502A" },
    sans: '"Geist", system-ui, sans-serif', mono: '"Geist Mono", ui-monospace, monospace',
  };
  const labelColor = (l) => C.opp[l] || C.opp.Medium;

  // ---- formatters ----
  const nf = new Intl.NumberFormat("en-IN");
  const int = (v) => (v == null ? "—" : nf.format(Math.round(v)));
  const r1 = (v) => (v == null ? "—" : Number(v).toFixed(1));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? esc(u) : "");        // block javascript: etc.
  const safeTel = (p) => esc(String(p || "").replace(/[^\d+()\-\s]/g, ""));     // digits/phone chars only

  // ---- topbar meta ----
  const setText = (id, t) => { const e = document.getElementById(id); if (e) e.textContent = t; };
  const genDate = D.generated_at ? new Date(D.generated_at) : null;
  const genStr = genDate ? genDate.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—";
  setText("m-city", D.city || "");
  setText("m-generated", "Updated " + genStr);
  setText("foot-generated", "Generated " + genStr + " · " + (D.kpis ? D.kpis.queries : 0) + " queries · " + (D.kpis ? int(D.kpis.total_appearances) : 0) + " appearances");

  // ---- empty state ----
  if (!D.clinics || !D.clinics.length) {
    app.innerHTML =
      '<div class="empty"><div class="box reveal d1">' +
      '<span class="eyebrow">No data yet</span>' +
      "<h1>Run the pipeline to see the market.</h1>" +
      "<p>Open the Streamlit console, load 50 queries, and click <b>Run Pipeline</b> — " +
      "or run <code>python run_pipeline.py</code>.</p>" +
      "<p>Then rebuild this view with <code>python derma_web.py</code>.</p>" +
      "</div></div>";
    return;
  }

  const k = D.kpis;
  const top = D.top10 || [];

  // ============================================================ render shell
  app.innerHTML = `
  <section class="hero wrap">
    <span class="eyebrow reveal d1">Market overview · ${esc((D.city || "").split(",")[0])}</span>
    <h1 class="reveal d1">${esc(D.headline_lead || "")} <span class="hl">${esc(D.headline_hl || "")}</span></h1>
    <p class="lede reveal d2">${esc(D.lede || "")}</p>
    <div class="kpis reveal d3" id="kpis"></div>
  </section>

  <section class="opportunity wrap">
    <div class="sec-head">
      <span class="eyebrow">Where the opportunity is</span>
      <h2>The ten clinics to approach first</h2>
      <p>Ranked by a 0–100 vulnerability score — the gap between a clinic's local demand and its online presence. Select one to see the case.</p>
    </div>
    <div class="opp-grid">
      <div class="opp-list" id="opp-list"></div>
      <aside class="opp-detail" id="opp-detail"></aside>
    </div>
  </section>

  <section class="landscape wrap">
    <div class="sec-head">
      <span class="eyebrow">Competitive landscape</span>
      <h2>Demand vs. reputation — coloured by who has a website</h2>
      <p>Every clinic placed by how often it surfaces in search (demand) against its review base (reputation). Bubble size is the vulnerability score. The large clay bubbles on the right are established, in-demand clinics with no website — your strongest leads.</p>
    </div>
    <div class="card reveal d1">
      <div class="legend" id="land-legend"></div>
      <div class="chart chart-xl" id="chart-landscape"></div>
    </div>
    <div class="insight"><span class="ic">◆</span><p id="land-insight"></p></div>
  </section>

  <section class="composition wrap">
    <div class="sec-head">
      <span class="eyebrow">Market composition</span>
      <h2>What the market looks like</h2>
      <p>Three readings of the field: where search demand concentrates, how complete clinics' online presence is, and how tightly reputation clusters.</p>
    </div>
    <div class="grid-3">
      <div class="card reveal d1"><div class="card-head"><div class="t">Online presence gap</div><div class="q">How many clinics have a website?</div></div><div class="chart chart-md" id="chart-website"></div></div>
      <div class="card reveal d2"><div class="card-head"><div class="t">Search demand by intent</div><div class="q">Which query types dominate?</div></div><div class="chart chart-md" id="chart-category"></div></div>
      <div class="card reveal d3"><div class="card-head"><div class="t">Reputation spread</div><div class="q">How are ratings distributed?</div></div><div class="chart chart-md" id="chart-rating"></div></div>
    </div>
    <div class="insight"><span class="ic">◆</span><p id="comp-insight"></p></div>
  </section>

  <section class="explore wrap">
    <div class="sec-head">
      <span class="eyebrow">Explore</span>
      <h2>All ${D.clinics.length} clinics</h2>
      <p>Search and sort the full field. Click a name to open it on Google Maps.</p>
    </div>
    <div class="tbl-toolbar">
      <div class="search">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
        <input id="tbl-search" type="text" placeholder="Search clinics…" />
      </div>
      <span class="count" id="tbl-count"></span>
    </div>
    <div class="tbl-shell"><table id="tbl"><thead></thead><tbody></tbody></table></div>
  </section>`;

  // ============================================================ KPIs
  document.getElementById("kpis").innerHTML = [
    { label: "Unique clinics", val: int(k.unique_clinics), ctx: `${int(k.total_appearances)} appearances across ${k.queries} searches` },
    { label: "No / weaker website", val: int(k.no_website_count), u: `/ ${k.unique_clinics}`, ctx: `${(100 - k.pct_with_website).toFixed(1)}% have no online home` },
    { label: "Avg rating", val: r1(k.avg_rating), u: "★", ctx: "Reputation is uniformly strong" },
    { label: "Average reviews", val: int(k.avg_reviews), ctx: "Mean social-proof base" },
  ].map((x) => `<div class="kpi"><span class="label">${x.label}</span><span class="val">${x.val}${x.u ? `<span class="u">${x.u}</span>` : ""}</span><span class="ctx">${x.ctx}</span></div>`).join("");

  // ============================================================ opportunity list + detail
  const maxScore = Math.max(...top.map((c) => c.score), 1);
  document.getElementById("opp-list").innerHTML = top.map((c, i) => {
    const col = labelColor(c.label);
    const site = c.has_website ? '<span class="site">● website</span>' : '<span class="nosite">● no / weaker site</span>';
    return `<div class="opp-row" data-i="${i}" data-clinic="${esc(c.name)}">
      <span class="rank">${i + 1}</span>
      <div><div class="name" title="${esc(c.name)}">${esc(c.display_name || c.name)}</div>
        <div class="facts"><span>★ ${r1(c.rating)}</span><span>${int(c.reviews)} rev</span><span>${int(c.appearances)} searches</span>${site}</div></div>
      <div class="score-cell"><span class="score-bar"><i style="width:${(c.score / maxScore) * 100}%;background:${col}"></i></span><span class="score-num">${c.score}</span></div>
    </div>`;
  }).join("");

  function renderDetail(i) {
    const c = top[i]; if (!c) return;
    const col = labelColor(c.label);
    document.getElementById("opp-detail").innerHTML = `
      <span class="tag" style="background:${col}">${esc(c.label)} · ${c.score}</span>
      <h3 title="${esc(c.name)}">${esc(c.display_name || c.name)}</h3>
      <div class="addr">${esc(c.address || "Address unavailable")}</div>
      <div class="statgrid">
        <div class="s"><div class="k">Rating</div><div class="v">${r1(c.rating)}★</div></div>
        <div class="s"><div class="k">Reviews</div><div class="v">${int(c.reviews)}</div></div>
        <div class="s"><div class="k">Appears in</div><div class="v">${int(c.appearances)}/${k.queries}</div></div>
        <div class="s"><div class="k">Website</div><div class="v" style="color:${c.has_website ? C.accent : C.clay}">${c.has_website ? "Yes" : "None"}</div></div>
      </div>
      <div class="note">${esc(c.notes || "")}</div>
      <div class="actions">
        ${safeUrl(c.place_url) ? `<a class="btn primary" href="${safeUrl(c.place_url)}" target="_blank" rel="noopener">View on Google Maps ↗</a>` : ""}
        ${c.phone ? `<a class="btn" href="tel:${safeTel(c.phone)}">${esc(c.phone)}</a>` : ""}
      </div>`;
  }
  let activeIdx = 0;
  function setActive(i) {
    activeIdx = i;
    document.querySelectorAll(".opp-row").forEach((el) => el.classList.toggle("active", +el.dataset.i === i));
    renderDetail(i);
    highlightScatter(top[i].name);
  }
  document.getElementById("opp-list").addEventListener("click", (e) => {
    const row = e.target.closest(".opp-row"); if (row) setActive(+row.dataset.i);
  });

  // ============================================================ ECharts helpers
  const charts = [];
  function mk(id) { const el = document.getElementById(id); const c = echarts.init(el, null, { renderer: "canvas" }); charts.push(c); return c; }
  const axisCommon = {
    axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false },
    axisLabel: { color: C.ink3, fontFamily: C.mono, fontSize: 11 },
    splitLine: { lineStyle: { color: C.line2 } },
    nameTextStyle: { color: C.ink3, fontFamily: C.mono, fontSize: 11 },
  };
  const tip = {
    backgroundColor: C.surface, borderColor: C.line, borderWidth: 1,
    padding: [10, 12], textStyle: { color: C.ink, fontFamily: C.sans, fontSize: 12.5 },
    extraCssText: "box-shadow:0 6px 24px -8px rgba(24,22,12,.18);border-radius:11px;",
  };
  const baseAnim = { animationDuration: 720, animationEasing: "cubicOut" };

  // ---- landscape scatter ----
  const cl = D.clinics;
  const landData = cl.map((c) => ({
    value: [c.appearances, c.reviews || 0, Math.max(8, c.score * 0.42 + 6)],
    name: c.name, c,
    itemStyle: { color: c.has_website ? C.accent : C.clay, opacity: 0.82, borderColor: "#fff", borderWidth: 1 },
  }));
  const medApp = D.median_appearances || 0;
  document.getElementById("land-legend").innerHTML =
    `<span class="l"><span class="sw" style="background:${C.accent}"></span>Has website</span>` +
    `<span class="l"><span class="sw" style="background:${C.clay}"></span>No / weaker website</span>` +
    `<span class="l" style="color:var(--ink-3)">bubble = vulnerability score</span>`;
  const land = mk("chart-landscape");
  land.setOption(Object.assign({}, baseAnim, {
    grid: { left: 58, right: 28, top: 24, bottom: 52 },
    tooltip: Object.assign({ trigger: "item", formatter: (p) => {
      const c = p.data.c;
      return `<b style="font-size:13px">${esc(c.display_name || c.name)}</b><br/>` +
        `<span style="color:${C.ink2}">★ ${r1(c.rating)} · ${int(c.reviews)} reviews</span><br/>` +
        `<span style="font-family:${C.mono}">Appears in ${int(c.appearances)}/${k.queries} searches</span><br/>` +
        `<span style="font-family:${C.mono}">Website: <b style="color:${c.has_website ? C.accent : C.clay}">${c.has_website ? "yes" : "none"}</b> · score ${c.score}</span>`;
    } }, tip),
    xAxis: Object.assign({ type: "value", name: "Search appearances →", nameLocation: "middle", nameGap: 32, min: 0 }, axisCommon),
    yAxis: Object.assign({ type: "value", name: "Google reviews", nameLocation: "middle", nameGap: 42, min: 0 }, axisCommon),
    series: [{
      type: "scatter", data: landData, symbolSize: (v) => v[2],
      markLine: medApp ? {
        silent: true, symbol: "none", lineStyle: { color: C.ink3, type: "dashed", opacity: .5 },
        label: { color: C.ink3, fontFamily: C.mono, fontSize: 10, formatter: "median demand" },
        data: [{ xAxis: medApp }],
      } : undefined,
      emphasis: { scale: 1.25, itemStyle: { opacity: 1, shadowBlur: 12, shadowColor: "rgba(0,0,0,.18)" } },
    }],
  }));
  function highlightScatter(name) {
    const idx = cl.findIndex((c) => c.name === name);
    if (idx < 0) return;
    land.dispatchAction({ type: "downplay", seriesIndex: 0 });
    land.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: idx });
  }
  const noSiteRight = cl.filter((c) => !c.has_website && c.appearances >= medApp).length;
  document.getElementById("land-insight").innerHTML =
    `<b>${noSiteRight} clinics</b> sit at or above median demand yet have <b>no website</b> — high-intent patients are finding them on Maps, but there's no site to convert that attention. That is the core opportunity.`;

  // ---- website coverage ring ----
  mk("chart-website").setOption(Object.assign({}, baseAnim, {
    tooltip: Object.assign({ trigger: "item", formatter: (p) => `${p.name}: <b>${p.value}</b> (${p.percent}%)` }, tip),
    series: [{
      type: "pie", radius: ["62%", "84%"], center: ["50%", "52%"], avoidLabelOverlap: false,
      padAngle: 2, itemStyle: { borderRadius: 4 }, label: { show: false }, labelLine: { show: false },
      data: [
        { value: k.unique_clinics - k.no_website_count, name: "Has website", itemStyle: { color: C.accent } },
        { value: k.no_website_count, name: "No / weaker website", itemStyle: { color: C.clay } },
      ],
    }],
    graphic: [
      { type: "text", left: "center", top: "42%", style: { text: k.no_website_count + "/" + k.unique_clinics, fontFamily: C.mono, fontSize: 30, fontWeight: 500, fill: C.ink, textAlign: "center" } },
      { type: "text", left: "center", top: "60%", style: { text: "no / weaker website", fontFamily: C.mono, fontSize: 11, fill: C.ink3, textAlign: "center" } },
    ],
  }));

  // ---- category mix (ranked horizontal bar) ----
  const cats = (D.categories || []).slice().sort((a, b) => a.count - b.count);
  mk("chart-category").setOption(Object.assign({}, baseAnim, {
    grid: { left: 4, right: 36, top: 10, bottom: 6, containLabel: true },
    tooltip: Object.assign({ trigger: "axis", axisPointer: { type: "shadow" }, formatter: (p) => `${p[0].name}: <b>${p[0].value}</b> queries` }, tip),
    xAxis: Object.assign({ type: "value", splitLine: { lineStyle: { color: C.line2 } }, axisLabel: { color: C.ink3, fontFamily: C.mono, fontSize: 10 } }, {}),
    yAxis: { type: "category", data: cats.map((c) => c.category), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: C.ink2, fontSize: 11.5, width: 110, overflow: "truncate" } },
    series: [{
      type: "bar", data: cats.map((c) => c.count), barWidth: "58%",
      itemStyle: { color: C.accent, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: "right", color: C.ink3, fontFamily: C.mono, fontSize: 11 },
    }],
  }));

  // ---- rating distribution ----
  const rd = D.rating_distribution || [];
  mk("chart-rating").setOption(Object.assign({}, baseAnim, {
    grid: { left: 6, right: 12, top: 16, bottom: 24, containLabel: true },
    tooltip: Object.assign({ trigger: "axis", axisPointer: { type: "shadow" }, formatter: (p) => `${p[0].name}: <b>${p[0].value}</b> clinics` }, tip),
    xAxis: { type: "category", data: rd.map((b) => b.bin), axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false }, axisLabel: { color: C.ink3, fontFamily: C.mono, fontSize: 10 } },
    yAxis: Object.assign({ type: "value", minInterval: 1 }, axisCommon),
    series: [{ type: "bar", data: rd.map((b) => b.count), barWidth: "62%", itemStyle: { color: C.accent, borderRadius: [4, 4, 0, 0] } }],
  }));

  document.getElementById("comp-insight").innerHTML =
    `Ratings cluster between <b>4.5 and 5.0</b> — reputation is not the differentiator here. With <b>${(100 - k.pct_with_website).toFixed(0)}%</b> of clinics lacking a website, <b>digital presence</b> is where the field is won.`;

  // ============================================================ table
  const cols = [
    { k: "name", t: "Clinic", num: false },
    { k: "rating", t: "Rating", num: true },
    { k: "reviews", t: "Reviews", num: true },
    { k: "appearances", t: "Searches", num: true },
    { k: "has_website", t: "Website", num: false },
    { k: "score", t: "Score", num: true },
  ];
  let sortKey = "score", sortDir = -1, query = "";
  const thead = document.querySelector("#tbl thead");
  const tbody = document.querySelector("#tbl tbody");
  function renderHead() {
    thead.innerHTML = "<tr>" + cols.map((c) =>
      `<th class="${c.num ? "num" : ""}" data-k="${c.k}">${c.t}<span class="ar">${sortKey === c.k ? (sortDir < 0 ? "↓" : "↑") : ""}</span></th>`).join("") + "</tr>";
  }
  function rows() {
    let r = D.clinics.filter((c) => c.name.toLowerCase().includes(query));
    r.sort((a, b) => {
      let x = a[sortKey], y = b[sortKey];
      if (sortKey === "has_website") { x = x ? 1 : 0; y = y ? 1 : 0; }
      if (typeof x === "string") return sortDir * x.localeCompare(y);
      return sortDir * ((x || 0) - (y || 0));
    });
    return r;
  }
  function renderBody() {
    const r = rows();
    document.getElementById("tbl-count").textContent = r.length + " of " + D.clinics.length;
    tbody.innerHTML = r.map((c) => `<tr>
      <td><span class="nm" title="${esc(c.name)}">${safeUrl(c.place_url) ? `<a href="${safeUrl(c.place_url)}" target="_blank" rel="noopener">${esc(c.display_name || c.name)}</a>` : esc(c.display_name || c.name)}</span></td>
      <td class="num">${r1(c.rating)}</td>
      <td class="num">${int(c.reviews)}</td>
      <td class="num">${int(c.appearances)}</td>
      <td><span class="pill ${c.has_website ? "has" : "no"}">${c.has_website ? "yes" : "none"}</span></td>
      <td class="num">${c.score}</td>
    </tr>`).join("");
  }
  thead.addEventListener("click", (e) => {
    const th = e.target.closest("th"); if (!th) return;
    const kk = th.dataset.k;
    if (kk === sortKey) sortDir *= -1; else { sortKey = kk; sortDir = kk === "name" ? 1 : -1; }
    renderHead(); renderBody();
  });
  document.getElementById("tbl-search").addEventListener("input", (e) => { query = e.target.value.toLowerCase().trim(); renderBody(); });
  renderHead(); renderBody();

  // ============================================================ init
  setActive(0);
  window.addEventListener("resize", () => charts.forEach((c) => c.resize()));
})();
