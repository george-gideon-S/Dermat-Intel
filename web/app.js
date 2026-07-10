/* Derma Intel — private report app (v2 "Luminous Precision").
   Two views: Your Clinic / The Market. Renders into #app via DI.renderApp(view);
   topbar nav lives in template.html and is wired here. Chart doctrine: BRAND_GUIDE_V2 §10 —
   categorical = triad deep stops + ink for "you"; magnitude = intensity of ONE hue;
   grid hairlines; mono micro axis labels; hero numerals are Doto (CSS .dot-num). */
(function () {
  "use strict";
  const D = window.__DATA__ || {};
  const CL = D.clinics || [];
  const MK = D.market || {};
  const K = D.kpis || {};
  const QN = (K.queries || 80);
  const WA = (D.contact || {}).whatsapp || "";
  const root = document.getElementById("app");

  // ---------- helpers ----------
  const nf = new Intl.NumberFormat("en-IN");
  const int = (v) => (v == null ? "—" : nf.format(Math.round(v)));
  const r1 = (v) => (v == null ? "—" : Number(v).toFixed(1));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // v2 palette (mirrors tokens-v2.css; ECharts needs literals)
  const C = { ink: "#131417", ink2: "#5C6066", ink3: "#9FA3A9", line: "rgba(19,20,23,.10)",
    grid: "rgba(19,20,23,.05)", lime: "#D9F24F",
    growth: "#2E9E44", slate: "#97A2B2", alert: "#EE6D96", orange: "#ED9A3E",
    gap: "rgba(19,20,23,.07)",
    mono: '"Geist Mono",monospace', sans: '"Geist",sans-serif',
    cat: ["#2E9E44", "#97A2B2", "#EE6D96", "#ED9A3E"] };
  // glass-pill tooltip (guide §10)
  const tip = { backgroundColor: "rgba(255,255,255,.85)", borderColor: "rgba(255,255,255,.65)", borderWidth: 1,
    textStyle: { color: C.ink, fontFamily: C.sans, fontSize: 12 },
    extraCssText: "border-radius:999px;box-shadow:0 24px 56px -20px rgba(19,20,23,.22);padding:8px 14px;backdrop-filter:blur(14px)" };
  const SERP = (f) => "proof/" + encodeURIComponent(f || "");
  const median = (a) => { const s = a.slice().sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0; };
  const waBtn = (label, msg, primary) => WA
    ? `<a class="btn ${primary ? "btn--primary" : ""}" target="_blank" rel="noopener"
         href="https://wa.me/${WA}?text=${encodeURIComponent(msg)}">${label}</a>`
    : `<button class="btn ${primary ? "btn--primary" : ""}">${label}</button>`;

  // ---------- state ----------
  const state = { idx: 0 };
  let CHARTS = [];
  function disposeCharts() { CHARTS.forEach((c) => { try { c.dispose(); } catch (e) {} }); CHARTS = []; }
  function mk(id, opt) { const el = document.getElementById(id); if (!el || !window.echarts) return; const c = echarts.init(el); c.setOption(opt); CHARTS.push(c); }
  const axis = { axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false },
    axisLabel: { color: C.ink2, fontFamily: C.mono, fontSize: 10 }, splitLine: { lineStyle: { color: C.grid } } };

  // ---------- client-side derivations ----------
  const AREAS = ["Brodipet", "Kothapet", "Lakshmipuram", "Arundelpet", "Pattabhipuram", "Nagarampalem",
    "Gujjanagundla", "Chuttugunta", "AT Agraharam", "SVN Colony", "Brindavan Gardens", "Sangadigunta", "Etukuru"];
  function areaOf(addr) { const a = (addr || ""); for (const x of AREAS) if (a.toLowerCase().includes(x.toLowerCase())) return x; return "Other"; }
  function percentileText(rank, total) { if (!rank || !total || total < 2) return ""; const below = Math.round((rank - 1) / (total - 1) * 10); return `more visible than ${10 - below} in 10 clinics`; }
  function fixesOf(c) {
    const COPY = { website: "Build a professional website", search: "Get your site ranking in Google search",
      maps: "Strengthen your Google Maps listing", reviews: "Close the Google reviews gap",
      phone: "Add a phone number patients can call", breadth: "Show up across more patient searches" };
    return (c.breakdown || []).map((b) => ({ key: b.key, label: COPY[b.key] || b.label, lift: Math.round(b.max - b.earned) }))
      .filter((x) => x.lift >= 2).sort((a, b) => b.lift - a.lift);
  }

  // ---------- render ----------
  const DI = (window.DI = window.DI || {});
  DI.renderApp = function (vw) {
    disposeCharts();
    DI.view = vw || DI.view || "clinic";
    document.querySelectorAll(".topbar [data-nav]").forEach((b) => {
      if (b.classList.contains("pill-tab")) b.classList.toggle("is-active", b.dataset.nav === DI.view);
    });
    root.innerHTML = `<div class="appmain">${DI.view === "market" ? marketView() : clinicView()}</div>`;
    wire();
    if (DI.view === "market") marketCharts(); else clinicCharts();
    window.requestAnimationFrame(() => CHARTS.forEach((c) => c.resize()));
  };

  // ============================================================ YOUR CLINIC
  function dumbbellRow(label, sub, you, mkt, fmt) {
    const max = Math.max(you || 0, mkt || 0) * 1.15 || 1;
    const px = (v) => Math.min(96, Math.max(3, (v || 0) / max * 100));
    const yl = px(you), ml = px(mkt);
    return `<div class="db">
      <div><span class="db-label">${label}</span><span class="db-sub">${sub}</span></div>
      <div class="db-track"><div class="db-rule"></div>
        <div class="db-line" style="left:${Math.min(yl, ml)}%; width:${Math.abs(yl - ml)}%"></div>
        <span class="db-dot mkt" style="left:${ml}%"></span>
        <span class="db-dot you" style="left:${yl}%"></span>
        <span class="db-val" style="left:${ml}%">${fmt(mkt)} mkt</span>
        <span class="db-val" style="left:${yl}%; bottom:-16px; color:var(--ink)">${fmt(you)} you</span>
      </div></div>`;
  }
  function intentRows(c) {
    const mkts = D.intents_market || {};
    const mine = {}; (c.intents || []).forEach((e) => mine[e.cat] = e);
    const cats = Object.keys(mkts).sort((a, b) => (mine[b] ? 1 : 0) - (mine[a] ? 1 : 0) || (mkts[a] - mkts[b]));
    const x = (pos) => Math.min(97, Math.max(2, (pos - 1) / 14 * 100));
    return cats.slice(0, 7).map((cat) => {
      const m = mkts[cat], e = mine[cat];
      if (!e) return `<div class="intent is-ghost">
        <span class="in-label">${esc(cat)}</span>
        <div class="in-track"><span class="in-mkt" style="left:${x(m)}%"></span>
          <span class="in-note">not seen — patients never find you here</span></div></div>`;
      return `<div class="intent">
        <span class="in-label">${esc(cat)}</span>
        <div class="in-track">
          <span class="in-mkt" style="left:${x(m)}%"></span>
          <span class="in-you" style="left:${x(e.pos)}%"></span>
          <span class="in-val" style="left:${x(e.pos)}%">#${e.pos}</span>
        </div></div>`;
    }).join("");
  }
  function clinicView() {
    const c = CL[state.idx] || CL[0]; if (!c) return "<p>No data.</p>";
    const total = c.visibility_total || CL.length;
    const rank = c.visibility_rank || "—";
    const vis = c.visibility != null ? c.visibility : 0;
    const opts = CL.map((x, i) => `<option value="${i}" ${i === state.idx ? "selected" : ""}>${esc(x.display_name || x.name)}</option>`).join("");
    const checks = (c.scorecard || []).map((s) => {
      const st = s.status === "good" ? "good" : s.status === "warn" ? "warn" : "miss";
      const word = st === "good" ? "In place" : st === "warn" ? "Partial" : "Missing";
      return `<div class="check is-${st}"><div class="k">${esc(s.label)}</div>
        <div class="v">${esc(s.value)}</div><span class="st">${word}</span>
        <div class="note">${esc(s.note)}</div></div>`;
    }).join("");
    const web = c.web || {};
    const proof = c.proof;
    const fixes = fixesOf(c);
    const topLift = fixes.slice(0, 2).reduce((s, f) => s + f.lift, 0);
    const nlp = c.nlp;
    const bm = {}; (c.benchmarks || []).forEach((b) => bm[b.key] = b);
    const name = c.display_name || c.name;
    return `
    <div class="selector"><span class="eyebrow">The examination · report for</span>
      <select id="sel">${opts}</select><span class="dim">${esc(areaOf(c.address))} · ${esc(String((D.generated_at || "")).slice(0, 10))}</span></div>

    <div class="clinic-hero">
      <div class="grain-card grain-card--status hero-score">
        <span class="gc-label">Online visibility</span>
        <span class="dot-num">${vis}</span>
        <span class="gc-sub">out of 100 · higher is better</span>
        <div class="ruler ruler--on-field" style="color:#fff"><span class="ruler-marker" style="--pos:${vis}%"></span></div>
      </div>
      <div class="hero-facts">
        <span class="rank-line">Rank #${rank} of ${total}</span>
        <span class="caption">${esc(percentileText(rank, total))} · ${esc(name)}</span>
        <div class="verdict">${esc(c.verdict || "")}</div>
      </div>
    </div>

    <section class="section"><div class="h2">Your 5-point examination</div>
      <div class="scorecard">${checks}</div></section>

    ${proof ? `<section class="card section proof"><div class="h2">What patients actually see</div>
      <img src="${SERP(proof.screenshot)}" alt="Google search result for ${esc(proof.query)}">
      <p class="caption">Search “${esc(proof.query)}” — <b>you're not here.</b> Patients find ${esc((proof.present || []).slice(0, 3).join(", "))}.</p>
      <div class="leak"><b>${QN}</b><span>searches</span> → <span>you appear in</span> <b>${web.appearances || 0}</b> → <span>your own site in</span> <b>${web.owned || 0}</b></div></section>` : ""}

    <section class="grid2 section">
      <div class="card"><div class="h2" style="font-size:1.1rem">You vs the market</div>
        <div class="dumbbells" style="margin-top:var(--sp-5)">
          ${dumbbellRow("Reviews", "count on Google", (bm.reviews || {}).you, (bm.reviews || {}).market, int)}
          ${dumbbellRow("Rating", "average stars", (bm.rating || {}).you, (bm.rating || {}).market, r1)}
          ${dumbbellRow("Demand", "searches shown in", c.appearances, (bm.demand || {}).market, int)}
        </div>
        <p class="caption" style="margin-top:var(--sp-4)">Ink dot = you · gray dot = market. The line is your gap.</p></div>
      <div class="card"><div class="h2" style="font-size:1.1rem">Where your score comes from</div>
        <div class="chart" id="ch-break"></div>
        <p class="caption">Filled = earned. Faint = the gap — that's your to-do list.</p></div>
    </section>

    <section class="card section"><div class="h2" style="font-size:1.1rem">Where you rank, by what patients want</div>
      <div class="intents" style="margin-top:var(--sp-4)">${intentRows(c)}</div>
      <p class="caption">Your average position (ink dot, #1 is best) vs the market median (gray tick),
      across ${QN} real queries grouped by patient intent. Ghost rows are demand you never appear for.</p></section>

    ${nlp ? `<section class="card section"><div class="h2" style="font-size:1.1rem">Patient voice · ${int(nlp.n)} reviews read</div>
      <div class="voice-strip" style="margin:var(--sp-3) 0">
        <div class="vs-pos" style="width:${Math.round(nlp.pos || 0)}%"></div>
        <div class="vs-neg" style="width:${Math.round(nlp.neg || 0)}%"></div></div>
      <p class="caption">${Math.round(nlp.pos || 0)}% positive · ${Math.round(nlp.neg || 0)}% negative ·
        ${Math.round((nlp.referral || 0) * 100)}% mention being referred${nlp.recent6mo != null ? ` · ${int(nlp.recent6mo)} reviews in the last 6 months` : ""}</p>
      <p style="margin-top:var(--sp-2)">Patients praise ${(nlp.themes || []).slice(0, 3).map((t) => `<span class="chip chip--good">${esc(String(t).replace(/_/g, " "))}</span>`).join(" ") || "—"}</p>
      ${(nlp.pains || []).length ? `<p style="margin-top:var(--sp-2)">Watch-outs ${nlp.pains.slice(0, 2).map((t) => `<span class="chip chip--bad">${esc(String(t).replace(/_/g, " "))}</span>`).join(" ")}</p>` : ""}</section>` : ""}

    <section class="section"><div class="h2">Treatment plan — what to fix first</div>
      <div class="recs">${fixes.length ? fixes.map((f) => `<div class="rec"><span>${esc(f.label)}</span><span class="lift">+${f.lift}</span></div>`).join("") : '<div class="rec"><span>You\'re in good shape online — keep reviews fresh.</span></div>'}</div>
      ${topLift >= 8 ? `<div class="whatif"><b>What-if:</b> treat the top two and your visibility could rise from <b>${vis}</b> to <b>~${Math.min(100, vis + topLift)}</b> (estimated).</div>` : ""}
      <div class="row" style="margin-top:var(--sp-3)">
        ${waBtn("Book the walkthrough →", `Namaste Trinade! Walkthrough for the ${name} report, please.`, true)}
        ${waBtn("Ask about a website build", `Namaste Trinade! Website build for ${name} — what are the next steps?`, false)}
      </div>
      <details class="method"><summary>How we measured this</summary><p class="caption">Checked across ${QN} patient searches on Google (Maps + Search). Visibility is an index of website, search ranking, Maps presence, reviews, phone and breadth — see The Market for the full picture.</p></details></section>`;
  }
  function clinicCharts() {
    const c = CL[state.idx] || CL[0]; if (!c) return;
    const labels = (c.breakdown || []).map((b) => b.label);
    mk("ch-break", { grid: { left: 130, right: 20, top: 10, bottom: 20 }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value", max: 30 }, axis),
      yAxis: Object.assign({ type: "category", data: labels, axisLabel: { color: C.ink2, fontSize: 11, fontFamily: C.sans } }, axis),
      series: [
        { name: "earned", type: "bar", stack: "t", data: (c.breakdown || []).map((b) => b.earned), itemStyle: { color: C.growth, borderRadius: [6, 0, 0, 6] } },
        { name: "gap", type: "bar", stack: "t", data: (c.breakdown || []).map((b) => b.max - b.earned), itemStyle: { color: C.gap, borderRadius: [0, 6, 6, 0] } },
      ] });
  }

  // ============================================================ THE MARKET (full redo = Phase D)
  let sortKey = "visibility", sortDir = -1, areaFilter = "All";
  function marketView() {
    const you = CL[state.idx] || CL[0];
    const revs = CL.map((c) => c.reviews || 0);
    const areas = ["All", ...Array.from(new Set(CL.map((c) => areaOf(c.address)))).sort()];
    return `
    <section class="section"><div class="row"><span class="eyebrow">The market · Guntur</span>
      ${you ? `<span class="youchip">You: ${esc(you.display_name || you.name)} · #${you.visibility_rank} · Vis ${you.visibility}</span>` : ""}</div>
      <div class="stats" style="margin-top:var(--sp-2)">
        <div class="stat"><div class="n">${MK.total || CL.length}</div><div class="c">clinics</div></div>
        <div class="stat"><div class="n">${MK.zero_web_presence}</div><div class="c">invisible in search (${MK.no_website_pct || 0}% no site)</div></div>
        <div class="stat"><div class="n">${MK.own_site}</div><div class="c">rank their own site</div></div>
        <div class="stat"><div class="n">${r1(MK.avg_rating)}</div><div class="c">avg rating ★</div></div>
        <div class="stat"><div class="n">${int(median(revs))}</div><div class="c">median reviews (mean ${int(MK.avg_reviews)} is skewed)</div></div>
      </div></section>

    <section class="card section"><div class="h2" style="font-size:1.1rem">Visibility league — who patients find</div>
      <div class="chart" id="ch-league" style="height:640px"></div>
      <p class="caption">All ${CL.length} clinics by online visibility (higher = better). <b>You're highlighted.</b> Dashed line = market median.</p></section>

    <section class="grid2 section">
      <div class="card"><div class="h2" style="font-size:1.1rem">Demand vs visibility</div><div class="chart" id="ch-quad"></div>
        <p class="caption">High demand + low visibility (bottom-right) = the biggest upside. Your dot is highlighted.</p></div>
      <div class="card"><div class="h2" style="font-size:1.1rem">How clinics get found</div><div class="chart" id="ch-found"></div>
        <p class="caption">Most clinics don't <i>own</i> their visibility — they rent it via directories, or have none.</p></div>
    </section>

    <section class="card section"><div class="h2" style="font-size:1.1rem">What patients search for</div><div class="chart" id="ch-cat"></div>
      <p class="caption">Where demand concentrates across our ${QN} queries.</p></section>

    <section class="section"><div class="h2">All clinics</div>
      <div class="seg">Filter by area: <select id="area">${areas.map((a) => `<option ${a === areaFilter ? "selected" : ""}>${esc(a)}</option>`).join("")}</select>
        <span class="dim">click a column to sort · click a clinic to open its report</span></div>
      <div class="tbl-wrap">${table()}</div>
      <details class="method" style="margin-top:var(--sp-2)"><summary>Caveats &amp; method</summary><p class="caption">Demand = appearances across ${QN} patient searches (a proxy, not exact volume). One snapshot. Only clinics that surfaced for our queries are included.</p></details></section>`;
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
      return `<tr class="${i === state.idx ? "you" : ""}">
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
      series: [{ type: "bar", barWidth: "62%", data: ordered.map(({ c, i }) => ({ value: c.visibility || 0, itemStyle: { color: i === state.idx ? C.ink : C.slate, borderRadius: [0, 5, 5, 0] } })),
        markLine: { silent: true, symbol: "none", data: [{ xAxis: med }], lineStyle: { color: C.ink3, type: "dashed" } } }] });
    mk("ch-quad", { grid: { left: 44, right: 20, top: 16, bottom: 40 }, tooltip: Object.assign({ trigger: "item", formatter: (p) => `${esc(p.data.name)}<br/>demand ${p.value[0]} · vis ${p.value[1]}` }, tip),
      xAxis: Object.assign({ type: "value", name: "searches shown in →", nameLocation: "middle", nameGap: 26 }, axis),
      yAxis: Object.assign({ type: "value", name: "visibility", max: 100 }, axis),
      series: [
        { type: "scatter", symbolSize: 9, data: CL.map((c) => ({ value: [c.appearances || 0, c.visibility || 0], name: c.display_name || c.name })), itemStyle: { color: "rgba(151,162,178,.6)" },
          markLine: { silent: true, symbol: "none", lineStyle: { color: C.ink3, type: "dashed" }, data: [{ xAxis: D.median_appearances || median(CL.map((c) => c.appearances || 0)) }, { yAxis: med }] } },
        { type: "scatter", symbolSize: 18, data: (CL[state.idx] ? [{ value: [CL[state.idx].appearances || 0, CL[state.idx].visibility || 0], name: "You" }] : []), itemStyle: { color: C.ink, borderColor: C.lime, borderWidth: 3 } },
      ] });
    const own = CL.filter((c) => c.web && c.web.has_own_site).length;
    const invis = CL.filter((c) => (c.web && c.web.appearances || 0) === 0).length;
    const borrowed = CL.filter((c) => c.web && !c.web.has_own_site && ((c.web.borrowed || 0) > 0 || (c.web.platforms || []).length)).length;
    const other = Math.max(0, CL.length - own - invis - borrowed);
    mk("ch-found", { grid: { left: 8, right: 16, top: 30, bottom: 8 }, legend: { top: 0, textStyle: { fontSize: 10, fontFamily: C.sans } }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value" }, axis), yAxis: { type: "category", data: ["Clinics"], axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
      series: [
        { name: "Rank own site", type: "bar", stack: "s", data: [own], itemStyle: { color: C.growth, borderRadius: [6, 0, 0, 6] } },
        { name: "Only via directories", type: "bar", stack: "s", data: [borrowed], itemStyle: { color: C.orange } },
        { name: "Other", type: "bar", stack: "s", data: [other], itemStyle: { color: C.ink3 } },
        { name: "Invisible", type: "bar", stack: "s", data: [invis], itemStyle: { color: C.alert, borderRadius: [0, 6, 6, 0] } },
      ] });
    const cats = (D.categories || []).slice().sort((a, b) => a.count - b.count);
    mk("ch-cat", { grid: { left: 8, right: 28, top: 8, bottom: 8, containLabel: true }, tooltip: Object.assign({ trigger: "axis" }, tip),
      xAxis: Object.assign({ type: "value" }, axis), yAxis: { type: "category", data: cats.map((c) => c.category), axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false }, axisLabel: { fontSize: 11, color: C.ink2, fontFamily: C.sans } },
      series: [{ type: "bar", barWidth: "62%", data: cats.map((c) => ({ value: c.count, itemStyle: { color: C.slate, borderRadius: [0, 6, 6, 0] } })),
        label: { show: true, position: "right", color: C.ink2, fontFamily: C.mono, fontSize: 10 } }] });
  }

  // ---------- wiring ----------
  document.querySelectorAll(".topbar [data-nav]").forEach((b) =>
    b.addEventListener("click", (e) => { e.preventDefault(); DI.renderApp(b.dataset.nav); }));
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
    root.querySelectorAll("[data-open]").forEach((o) => o.addEventListener("click", () => { state.idx = +o.dataset.open; DI.renderApp("clinic"); }));
  }

  window.addEventListener("resize", () => CHARTS.forEach((c) => c.resize()));
})();
