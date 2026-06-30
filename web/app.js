/* Derma Intel — tab app  ·  the two analytical screens (Your Clinic / All Clinics).
   The shell (shell.js) owns the top-bar nav + story; this file renders into #app via
   DI.renderApp(view) and draws the brand-coloured ECharts. Reads window.DI.data / __DATA__. */
(function () {
  "use strict";
  const D = window.__DATA__ || {};
  const CL = D.clinics || [];
  const MK = D.market || {};
  const K = D.kpis || {};
  const QN = (K.queries || 80);
  const root = document.getElementById("app");

  // ---------- helpers ----------
  const nf = new Intl.NumberFormat("en-IN");
  const int = (v) => (v == null ? "—" : nf.format(Math.round(v)));
  const r1 = (v) => (v == null ? "—" : Number(v).toFixed(1));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const C = { ink: "#0B0B0C", ink2: "#54504A", ink3: "#8A847B", line: "rgba(11,11,12,.10)",
    cobalt: "#1F6BF0", amber: "#FFB200", orange: "#FB5A1E", red: "#ED3A36", grass: "#16A64C",
    lavender: "#A98BF2", purple: "#9B3FEE",
    accent: "#9B3FEE", blue: "#1F6BF0", good: "#16A64C", warn: "#FFB200", bad: "#ED3A36",
    mono: '"Geist Mono",monospace', sans: '"Geist",sans-serif',
    cat: ["#1F6BF0", "#FB5A1E", "#16A64C", "#9B3FEE", "#FFB200", "#ED3A36", "#A98BF2"] };
  // brand tooltip — white card, hairline, soft shadow, Geist (BRAND_GUIDE.md §8)
  const tip = { backgroundColor: "#fff", borderColor: "rgba(11,11,12,.14)", borderWidth: 1,
    textStyle: { color: "#0B0B0C", fontFamily: '"Geist",sans-serif', fontSize: 12 },
    extraCssText: "border-radius:12px;box-shadow:0 10px 30px -12px rgba(0,0,0,.22);padding:8px 11px" };
  const SERP = (f) => "proof/" + encodeURIComponent(f || "");
  const median = (a) => { const s = a.slice().sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0; };

  // ---------- state ----------
  const state = { idx: 0 };
  let CHARTS = [];
  function disposeCharts() { CHARTS.forEach((c) => { try { c.dispose(); } catch (e) {} }); CHARTS = []; }
  function mk(id, opt) { const el = document.getElementById(id); if (!el || !window.echarts) return; const c = echarts.init(el); c.setOption(opt); CHARTS.push(c); }
  const axis = { axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false }, axisLabel: { color: C.ink2, fontFamily: C.mono, fontSize: 10 }, splitLine: { lineStyle: { color: "rgba(11,11,12,.06)" } } };

  // ---------- client-side derivations ----------
  const AREAS = ["Brodipet", "Kothapet", "Lakshmipuram", "Arundelpet", "Pattabhipuram", "Nagarampalem",
    "Gujjanagundla", "Chuttugunta", "AT Agraharam", "SVN Colony", "Brindavan Gardens", "Sangadigunta", "Etukuru"];
  function areaOf(addr) { const a = (addr || ""); for (const x of AREAS) if (a.toLowerCase().includes(x.toLowerCase())) return x; return "Other"; }
  function percentileText(rank, total) { if (!rank || !total || total < 2) return ""; const below = Math.round((rank - 1) / (total - 1) * 10); return `lower than ${below} in 10 clinics`; }
  function peersOf(c) {
    const rv = c.reviews || 0;
    let p = CL.filter((x) => x !== c && (x.reviews || 0) >= rv * 0.5 && (x.reviews || 0) <= rv * 1.5);
    if (p.length < 3) p = CL.filter((x) => x !== c);
    const avg = (f) => p.length ? p.reduce((s, x) => s + (f(x) || 0), 0) / p.length : 0;
    return { n: p.length, reviews: avg((x) => x.reviews), rating: avg((x) => x.rating), demand: avg((x) => x.appearances) };
  }
  function fixesOf(c) {
    const COPY = { website: "Build a professional website", search: "Get your site ranking in Google search",
      maps: "Strengthen your Google Maps listing", reviews: "Close the Google reviews gap",
      phone: "Add a phone number patients can call", breadth: "Show up across more patient searches" };
    return (c.breakdown || []).map((b) => ({ key: b.key, label: COPY[b.key] || b.label, lift: Math.round(b.max - b.earned) }))
      .filter((x) => x.lift >= 2).sort((a, b) => b.lift - a.lift);
  }

  // ---------- app render (shell.js owns top-bar nav + the story) ----------
  const DI = window.DI || (window.DI = {});
  DI.renderApp = function (vw) {
    disposeCharts();
    DI.view = vw || DI.view || "clinic";
    root.innerHTML = `<div class="appwrap"><span class="cursor-bg" id="cursor-bg" aria-hidden="true"></span>
      <div class="appmain reveal-app">${DI.view === "market" ? marketView() : clinicView()}</div></div>`;
    wire();
    if (DI.view === "market") marketCharts(); else clinicCharts();
    window.requestAnimationFrame(() => CHARTS.forEach((c) => c.resize()));
    initCursor();
  };

  // ============================================================ YOUR CLINIC
  function clinicView() {
    const c = CL[state.idx] || CL[0]; if (!c) return "<p>No data.</p>";
    const total = c.visibility_total || CL.length;
    const rank = c.visibility_rank || "—";
    const markerLeft = rank && total > 1 ? (1 - (rank - 1) / (total - 1)) * 100 : 50;
    const opts = CL.map((x, i) => `<option value="${i}" ${i === state.idx ? "selected" : ""}>${esc(x.display_name || x.name)}</option>`).join("");
    const checks = (c.scorecard || []).map((s) => {
      const sym = s.status === "good" ? "✓" : s.status === "warn" ? "!" : "✗";
      return `<div class="check is-${s.status}"><span class="st">${sym}</span><div class="k">${esc(s.label)}</div><div class="v">${esc(s.value)}</div><div class="note">${esc(s.note)}</div></div>`;
    }).join("");
    const web = c.web || {};
    const proof = c.proof;
    const fixes = fixesOf(c);
    const topLift = fixes.slice(0, 2).reduce((s, f) => s + f.lift, 0);
    const nlp = c.nlp;
    return `
    <div class="selector"><span class="eyebrow">Your clinic</span>
      <select id="sel">${opts}</select><span class="dim">example — pick yours</span></div>

    <div class="clinic-head">
      <div class="scorebox"><div class="eyebrow">Online visibility</div><div class="score-num">${c.visibility != null ? c.visibility : "—"}<small>/100</small></div></div>
      <div style="flex:1;min-width:240px">
        <div class="rank">Rank #${rank} of ${total}</div><div class="pct">${esc(percentileText(rank, total))}</div>
        <div class="marker"><i style="left:${markerLeft}%"></i></div>
        <div class="verdict">${esc(c.verdict || "")}</div>
        <div class="dim" style="font-size:13px;margin-top:4px">${esc(c.display_name || c.name)} · ${esc(areaOf(c.address))}</div>
      </div>
    </div>

    <section class="section"><div class="sec-head"><div class="h2">Your 5-point check</div></div>
      <div class="scorecard">${checks}</div></section>

    ${proof ? `<section class="card section proof"><div class="sec-head"><div class="h2">What patients actually see</div></div>
      <img src="${SERP(proof.screenshot)}" alt="SERP">
      <p class="caption">Search “${esc(proof.query)}” — <b>you're not here.</b> Patients find ${esc((proof.present || []).slice(0, 3).join(", "))}.</p>
      <div class="leak"><b>${QN} searches</b> → <span>you appear in</span> <b>${web.appearances || 0}</b> → <span>your own site in</span> <b>${web.owned || 0}</b></div></section>` : ""}

    <section class="grid2 section">
      <div class="card"><div class="h2" style="font-size:18px">You vs the market</div><div class="chart" id="ch-bench"></div>
        <p class="caption">Bars vs the Guntur average (100). Compared to <b>clinics like you</b> too.</p></div>
      <div class="card"><div class="h2" style="font-size:18px">Where your score comes from</div><div class="chart" id="ch-break"></div>
        <p class="caption">Filled = you have it. Faint = the gap — that's your to-do list.</p></div>
    </section>

    ${nlp ? `<section class="card section"><div class="h2" style="font-size:18px">Patient voice · ${int(nlp.n)} reviews</div>
      <p style="margin:6px 0"><b style="color:${C.good}">Patients praise:</b> ${(nlp.themes || []).slice(0, 3).map((t) => `<span class="chip chip--good">${esc(String(t).replace(/_/g, " "))}</span>`).join(" ") || "—"}</p>
      ${(nlp.pains || []).length ? `<p><b style="color:${C.bad}">Watch-outs:</b> ${nlp.pains.slice(0, 2).map((t) => `<span class="chip chip--bad">${esc(String(t).replace(/_/g, " "))}</span>`).join(" ")}</p>` : ""}
      <p class="caption">${Math.round(nlp.pos || 0)}% positive · ${Math.round((nlp.referral || 0) * 100)}% mention a referral.</p></section>` : ""}

    <section class="section"><div class="sec-head"><div class="h2">What to fix first</div></div>
      <div class="recs">${fixes.length ? fixes.map((f) => `<div class="rec"><span>${esc(f.label)}</span><span class="lift">+${f.lift} visibility</span></div>`).join("") : '<div class="rec"><span>You\'re in good shape online — keep reviews fresh.</span></div>'}</div>
      ${topLift >= 8 ? `<div class="whatif"><b>What-if:</b> tackle the top 2 and your visibility could rise from <b>${c.visibility}</b> to <b>~${Math.min(100, c.visibility + topLift)}</b> (estimated).</div>` : ""}
      <div class="row" style="margin-top:14px"><button class="btn btn--primary">Book a 15-min walkthrough →</button><button class="btn">Build my website</button></div>
      <details class="method"><summary>How we measured this</summary><p class="caption">Checked across ${QN} patient searches on Google (Maps + Search), June 2026. Visibility is an index of website, search ranking, Maps presence, reviews, phone and breadth — see All Clinics for the full market.</p></details></section>`;
  }
  function clinicCharts() {
    const c = CL[state.idx] || CL[0]; if (!c) return;
    const bm = {}; (c.benchmarks || []).forEach((b) => bm[b.key] = b);
    const pr = peersOf(c);
    const youP = [pct(bm.reviews), pct(bm.rating), pctv(c.appearances, (bm.demand || {}).market)];
    const peerP = [pctv(pr.reviews, (bm.reviews || {}).market), pctv(pr.rating, (bm.rating || {}).market), pctv(pr.demand, (bm.demand || {}).market)];
    function pct(b) { return b && b.market ? Math.round(b.you / b.market * 100) : 0; }
    function pctv(you, m) { return m ? Math.round((you || 0) / m * 100) : 0; }
    mk("ch-bench", { grid: { left: 40, right: 16, top: 28, bottom: 24 }, legend: { top: 0, textStyle: { fontSize: 11 } },
      tooltip: Object.assign({ trigger: "axis" }, tip), xAxis: Object.assign({ type: "category", data: ["Reviews", "Rating", "Searches"] }, axis),
      yAxis: Object.assign({ type: "value", name: "% of market" }, axis),
      series: [
        { name: "You", type: "bar", data: youP, itemStyle: { color: C.purple, borderRadius: [6, 6, 0, 0] }, markLine: { silent: true, symbol: "none", data: [{ yAxis: 100 }], lineStyle: { color: C.ink3, type: "dashed" }, label: { formatter: "market avg", color: C.ink3, fontSize: 10 } } },
        { name: "Clinics like you", type: "bar", data: peerP, itemStyle: { color: C.ink3, borderRadius: [6, 6, 0, 0] } },
      ] });
    const labels = (c.breakdown || []).map((b) => b.label);
    mk("ch-break", { grid: { left: 130, right: 20, top: 10, bottom: 20 }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value", max: 30 }, axis), yAxis: Object.assign({ type: "category", data: labels, axisLabel: { color: C.ink2, fontSize: 11 } }, axis),
      series: [
        { name: "earned", type: "bar", stack: "t", data: (c.breakdown || []).map((b) => b.earned), itemStyle: { color: C.purple, borderRadius: [6, 0, 0, 6] } },
        { name: "gap", type: "bar", stack: "t", data: (c.breakdown || []).map((b) => b.max - b.earned), itemStyle: { color: "rgba(11,11,12,.08)", borderRadius: [0, 6, 6, 0] } },
      ] });
  }

  // ============================================================ ALL CLINICS
  let sortKey = "visibility", sortDir = -1, areaFilter = "All";
  function marketView() {
    const you = CL[state.idx] || CL[0];
    const revs = CL.map((c) => c.reviews || 0);
    const areas = ["All", ...Array.from(new Set(CL.map((c) => areaOf(c.address)))).sort()];
    return `
    <section class="section"><div class="row"><span class="eyebrow">The market · Guntur</span>
      ${you ? `<span class="youchip">You: ${esc(you.display_name || you.name)} · #${you.visibility_rank} · Vis ${you.visibility}</span>` : ""}</div>
      <div class="stats" style="margin-top:10px">
        <div class="stat"><div class="n">${MK.total || CL.length}</div><div class="c">clinics</div></div>
        <div class="stat"><div class="n">${MK.zero_web_presence}</div><div class="c">invisible in search (${MK.no_website_pct || 0}% no site)</div></div>
        <div class="stat"><div class="n">${MK.own_site}</div><div class="c">rank own site</div></div>
        <div class="stat"><div class="n">${r1(MK.avg_rating)}★</div><div class="c">avg rating</div></div>
        <div class="stat"><div class="n">${int(median(revs))}</div><div class="c">median reviews (mean ${int(MK.avg_reviews)} is skewed)</div></div>
      </div></section>

    <section class="card section"><div class="h2" style="font-size:18px">Visibility league — who patients find</div>
      <div class="chart" id="ch-league" style="height:640px"></div>
      <p class="caption">All ${CL.length} clinics by online visibility (higher = better). <b>You're highlighted.</b> Dashed line = market median.</p></section>

    <section class="grid2 section">
      <div class="card"><div class="h2" style="font-size:18px">Demand vs visibility</div><div class="chart" id="ch-quad"></div>
        <p class="caption">High demand + low visibility (bottom-right) = the biggest upside. Your dot is highlighted.</p></div>
      <div class="card"><div class="h2" style="font-size:18px">How clinics get found</div><div class="chart" id="ch-found"></div>
        <p class="caption">Most clinics don't <i>own</i> their visibility — they rent it via aggregators, or have none.</p></div>
    </section>

    <section class="card section"><div class="h2" style="font-size:18px">What patients search for</div><div class="chart" id="ch-cat"></div>
      <p class="caption">Where demand concentrates across our ${QN} queries.</p></section>

    <section class="section"><div class="sec-head"><div class="h2">All clinics</div></div>
      <div class="seg">Filter by area: <select id="area">${areas.map((a) => `<option ${a === areaFilter ? "selected" : ""}>${esc(a)}</option>`).join("")}</select>
        <span class="dim">click a column to sort · click a clinic to open its report</span></div>
      <div class="tbl-wrap">${table()}</div>
      <details class="method" style="margin-top:10px"><summary>Caveats &amp; method</summary><p class="caption">Demand = appearances across ${QN} patient searches (a proxy, not exact volume). One snapshot, June 2026. Only clinics that surfaced for our queries are included.</p></details></section>`;
  }
  function table() {
    const cols = [["name", "Clinic"], ["visibility", "Vis"], ["visibility_rank", "Rank"], ["has_website", "Site"],
      ["own", "Own"], ["found", "Found via"], ["reviews", "Rev"], ["rating", "★"], ["appearances", "Searches"]];
    let rows = CL.map((c, i) => ({ c, i })).filter(({ c }) => areaFilter === "All" || areaOf(c.address) === areaFilter);
    const val = (c, k) => k === "own" ? (c.web && c.web.has_own_site ? 1 : 0) : k === "found" ? ((c.web && c.web.platforms || []).join(",")) : k === "name" ? (c.display_name || c.name) : c[k];
    rows.sort((a, b) => { let x = val(a.c, sortKey), y = val(b.c, sortKey); if (typeof x === "string") return sortDir * x.localeCompare(y); return sortDir * ((x || 0) - (y || 0)); });
    const head = "<tr>" + cols.map(([k, l]) => `<th data-sort="${k}">${l}${sortKey === k ? (sortDir < 0 ? " ↓" : " ↑") : ""}</th>`).join("") + "</tr>";
    const body = rows.map(({ c, i }) => {
      const found = c.web && c.web.has_own_site ? "Own site" : (c.web && c.web.platforms || []).length ? c.web.platforms.join(", ") : "—";
      return `<tr class="row-x ${i === state.idx ? "you" : ""}">
        <td><span class="open" data-open="${i}">${esc(c.display_name || c.name)}</span></td>
        <td>${c.visibility}</td><td>#${c.visibility_rank}</td>
        <td><span class="pill ${c.has_website ? "yes" : "no"}">${c.has_website ? "yes" : "no"}</span></td>
        <td>${c.web && c.web.has_own_site ? "yes" : "—"}</td><td>${esc(found)}</td>
        <td>${int(c.reviews)}</td><td>${r1(c.rating)}</td><td>${int(c.appearances)}</td></tr>`;
    }).join("");
    return `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
  }
  function marketCharts() {
    const ordered = CL.map((c, i) => ({ c, i })).sort((a, b) => (a.c.visibility || 0) - (b.c.visibility || 0));
    const med = median(CL.map((c) => c.visibility || 0));
    mk("ch-league", { grid: { left: 150, right: 24, top: 6, bottom: 20 }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value", max: 100 }, axis),
      yAxis: Object.assign({ type: "category", data: ordered.map(({ c }) => (c.display_name || c.name).slice(0, 22)), axisLabel: { fontSize: 9, color: C.ink2 } }, axis),
      series: [{ type: "bar", barWidth: "62%", data: ordered.map(({ c, i }) => ({ value: c.visibility || 0, itemStyle: { color: i === state.idx ? C.purple : C.cobalt, borderRadius: [0, 5, 5, 0] } })),
        markLine: { silent: true, symbol: "none", data: [{ xAxis: med }], lineStyle: { color: C.ink3, type: "dashed" } } }] });
    mk("ch-quad", { grid: { left: 44, right: 20, top: 16, bottom: 40 }, tooltip: Object.assign({ trigger: "item", formatter: (p) => `${esc(p.data.name)}<br/>demand ${p.value[0]} · vis ${p.value[1]}` }, tip),
      xAxis: Object.assign({ type: "value", name: "searches shown in →", nameLocation: "middle", nameGap: 26 }, axis),
      yAxis: Object.assign({ type: "value", name: "visibility", max: 100 }, axis),
      series: [
        { type: "scatter", symbolSize: 9, data: CL.map((c) => ({ value: [c.appearances || 0, c.visibility || 0], name: c.display_name || c.name })), itemStyle: { color: "rgba(31,107,240,.55)" },
          markLine: { silent: true, symbol: "none", lineStyle: { color: C.ink3, type: "dashed" }, data: [{ xAxis: D.median_appearances || median(CL.map((c) => c.appearances || 0)) }, { yAxis: med }] } },
        { type: "scatter", symbolSize: 18, data: (CL[state.idx] ? [{ value: [CL[state.idx].appearances || 0, CL[state.idx].visibility || 0], name: "You" }] : []), itemStyle: { color: C.purple, borderColor: "#fff", borderWidth: 2 } },
      ] });
    const own = CL.filter((c) => c.web && c.web.has_own_site).length;
    const invis = CL.filter((c) => (c.web && c.web.appearances || 0) === 0).length;
    const borrowed = CL.filter((c) => c.web && !c.web.has_own_site && ((c.web.borrowed || 0) > 0 || (c.web.platforms || []).length)).length;
    const other = Math.max(0, CL.length - own - invis - borrowed);
    mk("ch-found", { grid: { left: 8, right: 16, top: 30, bottom: 8 }, legend: { top: 0, textStyle: { fontSize: 10, fontFamily: C.sans } }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value" }, axis), yAxis: { type: "category", data: ["Clinics"], axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
      series: [
        { name: "Rank own site", type: "bar", stack: "s", data: [own], itemStyle: { color: C.grass, borderRadius: [6, 0, 0, 6] } },
        { name: "Only via Practo/JustDial", type: "bar", stack: "s", data: [borrowed], itemStyle: { color: C.amber } },
        { name: "Other", type: "bar", stack: "s", data: [other], itemStyle: { color: C.ink3 } },
        { name: "Invisible", type: "bar", stack: "s", data: [invis], itemStyle: { color: C.red, borderRadius: [0, 6, 6, 0] } },
      ] });
    const cats = (D.categories || []).slice().sort((a, b) => a.count - b.count);
    mk("ch-cat", { grid: { left: 8, right: 28, top: 8, bottom: 8, containLabel: true }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value" }, axis), yAxis: { type: "category", data: cats.map((c) => c.category), axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false }, axisLabel: { fontSize: 11, color: C.ink2 } },
      series: [{ type: "bar", barWidth: "62%", data: cats.map((c, i) => ({ value: c.count, itemStyle: { color: C.cat[i % C.cat.length], borderRadius: [0, 6, 6, 0] } })), label: { show: true, position: "right", color: C.ink2, fontFamily: C.mono, fontSize: 10 } }] });
  }

  // ---------- wiring ----------
  function wire() {
    const sel = document.getElementById("sel");
    if (sel) sel.addEventListener("change", () => { state.idx = +sel.value; DI.renderApp("clinic"); });
    const area = document.getElementById("area");
    if (area) area.addEventListener("change", () => { areaFilter = area.value; document.querySelector(".tbl-wrap").innerHTML = table(); wireTable(); });
    wireTable();
  }
  function wireTable() {
    root.querySelectorAll("th[data-sort]").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.sort; if (k === sortKey) sortDir *= -1; else { sortKey = k; sortDir = k === "name" ? 1 : -1; }
      document.querySelector(".tbl-wrap").innerHTML = table(); wireTable();
    }));
    root.querySelectorAll("[data-open]").forEach((o) => o.addEventListener("click", () => { state.idx = +o.dataset.open; (DI.enterApp || DI.renderApp)("clinic"); }));
  }

  // ---------- cursor-tied background parallax ----------
  // Translate the composited .cursor-bg layer via inherited :root vars (GPU transform, CSS-smoothed).
  // Binds once globally so it survives tab re-renders (the layer reads the inherited vars).
  let cursorBound = false;
  function initCursor() {
    if (cursorBound || DI.reduced) return;
    cursorBound = true;
    const root = document.documentElement;
    window.addEventListener("pointermove", (e) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 30;
      const ny = (e.clientY / window.innerHeight - 0.5) * 30;
      root.style.setProperty("--mx", nx.toFixed(1) + "px");
      root.style.setProperty("--my", ny.toFixed(1) + "px");
    }, { passive: true });
  }

  window.addEventListener("resize", () => CHARTS.forEach((c) => c.resize()));
})();
