/* Derma Intel — ROUGH SKETCH (Phase 11 polishes design/motion).
   Three views (Home / Your Clinic / All Clinics) + onboarding tour. Reads window.__DATA__. */
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
  const C = { ink: "#16150F", ink2: "#57554B", ink3: "#908E82", line: "#E2E0D6", accent: "#0F766E",
    blue: "#1f6feb", orange: "#C8843F", good: "#0F766E", warn: "#B07A12", bad: "#B0542C",
    mono: '"Geist Mono",monospace', sans: '"Geist",sans-serif' };
  const SERP = (f) => "../../data/Full%20Page%20Screenshots/" + encodeURIComponent(f || "");
  const median = (a) => { const s = a.slice().sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0; };

  // a sample proof for the home teaser (first clinic that has one)
  const SAMPLE_PROOF = (CL.find((c) => c.proof && c.proof.screenshot) || {}).proof || null;

  // ---------- state ----------
  const state = { view: "home", idx: 0 };
  let CHARTS = [];
  function disposeCharts() { CHARTS.forEach((c) => { try { c.dispose(); } catch (e) {} }); CHARTS = []; }
  function mk(id, opt) { const el = document.getElementById(id); if (!el || !window.echarts) return; const c = echarts.init(el); c.setOption(opt); CHARTS.push(c); }
  const axis = { axisLine: { lineStyle: { color: C.line } }, axisTick: { show: false }, axisLabel: { color: C.ink3, fontFamily: C.mono, fontSize: 10 }, splitLine: { lineStyle: { color: "#EFEDE5" } } };

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
    // gaps from the visibility breakdown become the ranked fixes
    const COPY = { website: "Build a professional website", search: "Get your site ranking in Google search",
      maps: "Strengthen your Google Maps listing", reviews: "Close the Google reviews gap",
      phone: "Add a phone number patients can call", breadth: "Show up across more patient searches" };
    return (c.breakdown || []).map((b) => ({ key: b.key, label: COPY[b.key] || b.label, lift: Math.round(b.max - b.earned) }))
      .filter((x) => x.lift >= 2).sort((a, b) => b.lift - a.lift);
  }

  // ---------- shell ----------
  function setView(v) { state.view = v; render(); }
  function render() {
    disposeCharts();
    root.innerHTML = `<div class="layout">${sidebar()}<main class="main">${view()}</main></div>`;
    wire();
    if (state.view === "clinic") clinicCharts();
    if (state.view === "market") marketCharts();
    window.requestAnimationFrame(() => CHARTS.forEach((c) => c.resize()));
  }
  function sidebar() {
    return `<aside class="side">
      <div class="brand" data-go="home">Derma&nbsp;Intel<small>Guntur market intel</small></div>
      <button class="nav-home ${state.view === "home" ? "is-active" : ""}" data-go="home">⌂ Home</button>
      <div data-tour="tabs" style="display:flex;flex-direction:column;gap:10px">
        <button class="tab tab--clinic ${state.view === "clinic" ? "is-active" : ""}" data-go="clinic">
          <span class="tab-num">01</span><span class="tab-arrow">↗</span><span class="tab-label">Your Clinic</span></button>
        <button class="tab tab--market ${state.view === "market" ? "is-active" : ""}" data-go="market">
          <span class="tab-num">02</span><span class="tab-arrow">↗</span><span class="tab-label">All Clinics</span></button>
      </div>
      <button class="tour-btn" data-tour-start>◇ Take the tour</button>
      <div class="side-foot">${esc((D.generated_at || "").slice(0, 10))} · ${MK.total || CL.length} clinics</div>
    </aside>`;
  }
  function view() { return state.view === "clinic" ? clinicView() : state.view === "market" ? marketView() : homeView(); }

  // ============================================================ HOME
  function homeView() {
    return `<section class="hero section">
      <span class="eyebrow">Guntur · Dermatology</span>
      <h1 class="h1">Your patients are searching. Can they find you?</h1>
      <p class="lede">Derma Intel shows exactly how patients discover dermatology clinics in Guntur on Google — and where your clinic stands.</p>
      <div class="row"><button class="btn btn--primary" data-go="clinic">See your clinic →</button>
        <button class="btn" data-go="market">Explore the market</button></div>
    </section>
    <div class="trust"><b>How we know:</b> we ran <b>${QN} real patient searches</b> on Google (Maps + Search),
      recorded <b>who actually shows up</b>, and analysed <b>${MK.total || CL.length} clinics</b>. Snapshot: <b>June 2026</b>.
      <details style="margin-top:6px"><summary>What we can &amp; can't claim</summary>
      <p class="caption">It's a single snapshot in time and location. "Searches you show in" is a demand <i>proxy</i> from our query set — not exact patient volume. Reviews are Google-only.</p></details></div>
    <div class="facts">
      <div class="fact"><div class="n">${MK.total || CL.length}</div><div class="c">clinics mapped in Guntur</div></div>
      <div class="fact"><div class="n">${MK.zero_web_presence != null ? MK.zero_web_presence : "—"}</div><div class="c">are invisible in Google web search</div></div>
      <div class="fact"><div class="n">${MK.own_site != null ? MK.own_site : "—"}</div><div class="c">rank their own website</div></div>
    </div>
    ${SAMPLE_PROOF ? `<div class="card proofteaser section">
      <span class="eyebrow">See what patients see</span>
      <img src="${SERP(SAMPLE_PROOF.screenshot)}" alt="Google results">
      <p class="caption">When someone searches “${esc(SAMPLE_PROOF.query || "best dermatologist in Guntur")}”, this is the page they get. Is your clinic on it? <b data-go="clinic" style="cursor:pointer;text-decoration:underline">Check your clinic →</b></p></div>` : ""}
    <div class="doors">
      <div class="card door" data-go="clinic"><h3>① Your Clinic</h3><p class="muted">A personal report: your visibility score, where patients miss you, and what to fix.</p></div>
      <div class="card door" data-go="market"><h3>② All Clinics</h3><p class="muted">The whole Guntur market: who ranks, who's invisible, and how you compare.</p></div>
    </div>
    <p class="caption">How it works: <b>1</b> pick your clinic · <b>2</b> see your visibility + the proof · <b>3</b> get your tailored fixes.</p>`;
  }

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
    <div class="selector" data-tour="selector"><span class="eyebrow">Your clinic</span>
      <select id="sel">${opts}</select><span class="dim">example — pick yours</span></div>

    <div class="clinic-head" data-tour="score">
      <div class="scorebox"><div class="eyebrow">Online visibility</div><div class="score-num">${c.visibility != null ? c.visibility : "—"}<small>/100</small></div></div>
      <div style="flex:1;min-width:240px">
        <div class="rank">Rank #${rank} of ${total}</div><div class="pct">${esc(percentileText(rank, total))}</div>
        <div class="marker"><i style="left:${markerLeft}%"></i></div>
        <div class="verdict">${esc(c.verdict || "")}</div>
        <div class="dim" style="font-size:13px;margin-top:4px">${esc(c.display_name || c.name)} · ${esc(areaOf(c.address))}</div>
      </div>
    </div>

    <section class="section"><div class="sec-head"><div class="h2">Your 5-point check</div></div>
      <div class="scorecard" data-tour="scorecard">${checks}</div></section>

    ${proof ? `<section class="card section proof" data-tour="proof"><div class="sec-head"><div class="h2">What patients actually see</div></div>
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

    <section class="section" data-tour="fixes"><div class="sec-head"><div class="h2">What to fix first</div></div>
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
      tooltip: { trigger: "axis" }, xAxis: Object.assign({ type: "category", data: ["Reviews", "Rating", "Searches"] }, axis),
      yAxis: Object.assign({ type: "value", name: "% of market" }, axis),
      series: [
        { name: "You", type: "bar", data: youP, itemStyle: { color: C.blue }, markLine: { silent: true, symbol: "none", data: [{ yAxis: 100 }], lineStyle: { color: C.ink3, type: "dashed" }, label: { formatter: "market avg", color: C.ink3, fontSize: 10 } } },
        { name: "Clinics like you", type: "bar", data: peerP, itemStyle: { color: C.ink3 } },
      ] });
    const labels = (c.breakdown || []).map((b) => b.label);
    mk("ch-break", { grid: { left: 130, right: 20, top: 10, bottom: 20 }, tooltip: { trigger: "axis" },
      xAxis: Object.assign({ type: "value", max: 30 }, axis), yAxis: Object.assign({ type: "category", data: labels, axisLabel: { color: C.ink2, fontSize: 11 } }, axis),
      series: [
        { name: "earned", type: "bar", stack: "t", data: (c.breakdown || []).map((b) => b.earned), itemStyle: { color: C.accent } },
        { name: "gap", type: "bar", stack: "t", data: (c.breakdown || []).map((b) => b.max - b.earned), itemStyle: { color: "#E6E3D8" } },
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

    <section class="card section" data-tour="league"><div class="h2" style="font-size:18px">Visibility league — who patients find</div>
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
    mk("ch-league", { grid: { left: 150, right: 24, top: 6, bottom: 20 }, tooltip: { trigger: "axis" },
      xAxis: Object.assign({ type: "value", max: 100 }, axis),
      yAxis: Object.assign({ type: "category", data: ordered.map(({ c }) => (c.display_name || c.name).slice(0, 22)), axisLabel: { fontSize: 9, color: C.ink2 } }, axis),
      series: [{ type: "bar", data: ordered.map(({ c, i }) => ({ value: c.visibility || 0, itemStyle: { color: i === state.idx ? C.blue : C.accent } })),
        markLine: { silent: true, symbol: "none", data: [{ xAxis: med }], lineStyle: { color: C.ink3, type: "dashed" } } }] });
    mk("ch-quad", { grid: { left: 44, right: 20, top: 16, bottom: 40 }, tooltip: { trigger: "item", formatter: (p) => `${esc(p.data.name)}<br/>demand ${p.value[0]} · vis ${p.value[1]}` },
      xAxis: Object.assign({ type: "value", name: "searches shown in →", nameLocation: "middle", nameGap: 26 }, axis),
      yAxis: Object.assign({ type: "value", name: "visibility", max: 100 }, axis),
      series: [
        { type: "scatter", symbolSize: 9, data: CL.map((c) => ({ value: [c.appearances || 0, c.visibility || 0], name: c.display_name || c.name })), itemStyle: { color: "rgba(15,118,110,.5)" },
          markLine: { silent: true, symbol: "none", lineStyle: { color: C.ink3, type: "dashed" }, data: [{ xAxis: D.median_appearances || median(CL.map((c) => c.appearances || 0)) }, { yAxis: med }] } },
        { type: "scatter", symbolSize: 18, data: (CL[state.idx] ? [{ value: [CL[state.idx].appearances || 0, CL[state.idx].visibility || 0], name: "You" }] : []), itemStyle: { color: C.blue, borderColor: "#fff", borderWidth: 2 } },
      ] });
    const own = CL.filter((c) => c.web && c.web.has_own_site).length;
    const invis = CL.filter((c) => (c.web && c.web.appearances || 0) === 0).length;
    const borrowed = CL.filter((c) => c.web && !c.web.has_own_site && ((c.web.borrowed || 0) > 0 || (c.web.platforms || []).length)).length;
    const other = Math.max(0, CL.length - own - invis - borrowed);
    mk("ch-found", { grid: { left: 8, right: 16, top: 30, bottom: 8 }, legend: { top: 0, textStyle: { fontSize: 10 } }, tooltip: { trigger: "axis" },
      xAxis: Object.assign({ type: "value" }, axis), yAxis: { type: "category", data: ["Clinics"], axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
      series: [
        { name: "Rank own site", type: "bar", stack: "s", data: [own], itemStyle: { color: C.accent } },
        { name: "Only via Practo/JustDial", type: "bar", stack: "s", data: [borrowed], itemStyle: { color: C.orange } },
        { name: "Other", type: "bar", stack: "s", data: [other], itemStyle: { color: C.ink3 } },
        { name: "Invisible", type: "bar", stack: "s", data: [invis], itemStyle: { color: C.bad } },
      ] });
    const cats = (D.categories || []).slice().sort((a, b) => a.count - b.count);
    mk("ch-cat", { grid: { left: 8, right: 28, top: 8, bottom: 8, containLabel: true }, tooltip: { trigger: "axis" },
      xAxis: Object.assign({ type: "value" }, axis), yAxis: { type: "category", data: cats.map((c) => c.category), axisLabel: { fontSize: 11, color: C.ink2 } },
      series: [{ type: "bar", data: cats.map((c) => c.count), itemStyle: { color: C.accent, borderRadius: [0, 4, 4, 0] }, label: { show: true, position: "right", color: C.ink3, fontSize: 10 } }] });
  }

  // ---------- wiring ----------
  function wire() {
    root.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => setView(b.dataset.go)));
    root.querySelectorAll("[data-tour-start]").forEach((b) => b.addEventListener("click", () => startTour(true)));
    const sel = document.getElementById("sel");
    if (sel) sel.addEventListener("change", () => { state.idx = +sel.value; render(); });
    const area = document.getElementById("area");
    if (area) area.addEventListener("change", () => { areaFilter = area.value; document.querySelector(".tbl-wrap").innerHTML = table(); wireTable(); });
    wireTable();
  }
  function wireTable() {
    root.querySelectorAll("th[data-sort]").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.sort; if (k === sortKey) sortDir *= -1; else { sortKey = k; sortDir = k === "name" ? 1 : -1; }
      document.querySelector(".tbl-wrap").innerHTML = table(); wireTable();
    }));
    root.querySelectorAll("[data-open]").forEach((o) => o.addEventListener("click", () => { state.idx = +o.dataset.open; setView("clinic"); }));
  }

  // ============================================================ TOUR
  const TOUR = [
    { view: "home", sel: '[data-tour="tabs"]', title: "Two ways in", text: "Your Clinic = your own report. All Clinics = the whole Guntur market." },
    { view: "clinic", sel: '[data-tour="selector"]', title: "Pick a clinic", text: "Load any clinic's report. It defaults to an example you can change." },
    { view: "clinic", sel: '[data-tour="score"]', title: "Online Visibility", text: "0–100, higher is better — plus your rank among all 34 clinics." },
    { view: "clinic", sel: '[data-tour="scorecard"]', title: "Five quick checks", text: "Exactly where patients find you online — or don't." },
    { view: "clinic", sel: '[data-tour="proof"]', title: "The proof", text: "The real Google page patients see. Is your clinic on it?" },
    { view: "market", sel: '[data-tour="league"]', title: "Compare everyone", text: "Where you rank against all 34 — and the upside you're leaving on the table." },
  ];
  let tourEls = null;
  function startTour(force) {
    if (!force && localStorage.getItem("derma_tour_done")) return;
    if (!tourEls) {
      const ov = document.createElement("div"); ov.className = "tour-ov";
      ov.innerHTML = `<div class="tour-spot"></div><div class="tour-pop"><div class="tour-title"></div><div class="tour-text"></div>
        <div class="tour-actions"><span class="tour-step"></span><span><button class="tour-skip">Skip</button>
        &nbsp;<button class="btn btn--sm tour-next">Next</button></span></div></div>`;
      document.body.appendChild(ov);
      tourEls = { ov, spot: ov.querySelector(".tour-spot"), pop: ov.querySelector(".tour-pop"),
        title: ov.querySelector(".tour-title"), text: ov.querySelector(".tour-text"), step: ov.querySelector(".tour-step") };
      ov.querySelector(".tour-skip").addEventListener("click", endTour);
      ov.querySelector(".tour-next").addEventListener("click", () => showStep(window._ti + 1));
    }
    tourEls.ov.style.display = "block";
    showStep(0);
  }
  function showStep(i) {
    window._ti = i;
    if (i >= TOUR.length) return endTour();
    const s = TOUR[i];
    if (state.view !== s.view) setView(s.view);
    setTimeout(() => {
      const el = document.querySelector(s.sel);
      if (!el) return showStep(i + 1);
      el.scrollIntoView({ block: "center", behavior: "instant" in document.documentElement.style ? "instant" : "auto" });
      setTimeout(() => {
        const r = el.getBoundingClientRect(), pad = 8;
        const sp = tourEls.spot; sp.style.left = (r.left - pad) + "px"; sp.style.top = (r.top - pad) + "px";
        sp.style.width = (r.width + pad * 2) + "px"; sp.style.height = (r.height + pad * 2) + "px";
        tourEls.title.textContent = s.title; tourEls.text.textContent = s.text;
        tourEls.step.textContent = `${i + 1} / ${TOUR.length}`;
        const pop = tourEls.pop; const top = Math.min(window.innerHeight - 150, r.bottom + 12);
        pop.style.top = top + "px"; pop.style.left = Math.min(window.innerWidth - 320, Math.max(12, r.left)) + "px";
        tourEls.ov.querySelector(".tour-next").textContent = i === TOUR.length - 1 ? "Done" : "Next";
      }, 30);
    }, state.view !== s.view ? 90 : 0);
  }
  function endTour() { if (tourEls) tourEls.ov.style.display = "none"; localStorage.setItem("derma_tour_done", "1"); }

  // ---------- init ----------
  if (!CL.length) { root.innerHTML = '<div class="main"><h1>No data yet.</h1><p>Run <code>python run_pipeline.py</code> then <code>python derma_web.py</code>.</p></div>'; return; }
  render();
  window.addEventListener("resize", () => CHARTS.forEach((c) => c.resize()));
  setTimeout(() => startTour(false), 400);
})();
