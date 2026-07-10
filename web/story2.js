/* ============================================================================
   Derma Intel — public home story (v2 "Luminous Precision").
   Six acts: hook → market swarm (pinned split) → teasers → turn → gate → offer.
   Data: window.__DATA__ = the ANONYMIZED public payload (web/public_data.py).
   No clinic names exist client-side; the gate matches salted FNV-1a hashes.
   ============================================================================ */
(function () {
  "use strict";
  const D = window.__DATA__ || {};
  const K = D.kpis || {};
  const P = D.pricing || {};
  const reduced = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  const hasGsap = typeof gsap !== "undefined";
  if (hasGsap && typeof ScrollTrigger !== "undefined") gsap.registerPlugin(ScrollTrigger);

  /* ---------- utils ---------- */
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");

  // FNV-1a 32-bit — MUST mirror web/public_data.py::fnv1a
  function fnv1a(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h = Math.imul(h ^ s.charCodeAt(i), 16777619) >>> 0;
    }
    return h >>> 0;
  }
  const STOP = new Set(["clinic","clinics","skin","hair","care","dr","doctor","the","and",
    "centre","center","hospital","derma","dermatology","dermatologist","cosmetic","laser","guntur"]);
  const tokens = (s) => ((s || "").toLowerCase().match(/[a-z0-9]+/g) || [])
    .filter((t) => t.length >= 3 && !STOP.has(t));
  const normFull = (s) => ((s || "").toLowerCase().match(/[a-z0-9]+/g) || []).join("");

  function waLink(msg) {
    return P.whatsapp ? `https://wa.me/${P.whatsapp}?text=${encodeURIComponent(msg)}` : "";
  }
  // CTA fallback chain: Razorpay link → WhatsApp → scroll to offer/footer.
  function payHref(link, waMsg) {
    if (link) return { href: link, ext: true };
    const wa = waLink(waMsg);
    if (wa) return { href: wa, ext: true };
    return { href: "#offer", ext: false };
  }
  const A = (o, label, cls) =>
    `<a class="btn ${cls}" href="${esc(o.href)}"${o.ext ? ' target="_blank" rel="noopener"' : ""}>${label}</a>`;

  function countUp(el, target, dur) {
    const t = Number(target) || 0;
    if (reduced || !hasGsap) { el.textContent = String(t); return; }
    const o = { v: 0 };
    gsap.to(o, {
      v: t, duration: (dur || 520) / 1000, ease: "power3.out",
      onUpdate: () => { el.textContent = String(Math.round(o.v)); },
    });
  }

  /* ---------- build the DOM ---------- */
  const root = document.getElementById("story2");
  const nClinics = K.unique_clinics || 0;
  const nInvisible = K.no_website_count || 0;
  const nQueries = K.queries || 0;
  const ob = D.owned_borrowed || { owned: 0, borrowed_only: 0, invisible: 0 };
  const obTotal = Math.max(ob.owned + ob.borrowed_only + ob.invisible, 1);

  const teaserHTML = (D.teasers || []).map((t) => `
    <div class="grain-card grain-card--alert teaser" style="--field-dim:.85">
      <span class="dot-num t-letter">${esc(t.letter)}</span>
      <div class="t-meta">
        <span class="gc-label">Clinic ${esc(t.letter)}</span>
        <span class="gc-sub">${esc(t.rating_band || "")}★ · ${esc(t.reviews_band)} reviews · ${t.demand === "high" ? "high" : "steady"} patient demand</span>
        <span class="gc-sub" style="font-weight:600">Zero web presence.</span>
      </div>
    </div>`).join("");

  const turnRow = (label, note, count, color) => `
    <div class="trow">
      <div><div class="tr-label">${label}</div><div class="tr-note">${note}</div></div>
      <div class="tr-bar" data-w="${(count / obTotal)}" style="background:${color}"></div>
      <span class="dot-num" data-count="${count}">${count}</span>
    </div>`;

  root.innerHTML = `
  <section class="act" id="top">
    <span class="chip-lime act-kicker">Guntur · live market scan</span>
    <h1 id="hook-h1">Your patients are searching. Right now.</h1>
    <div class="ticker"><span class="q" id="ticker-q"></span><span class="caret"></span></div>
    <div class="hook-count">
      <span class="dot-num" id="hook-n">0</span>
      <span class="micro-label">high-intent searches mapped this quarter</span>
    </div>
  </section>

  <section class="act" id="market">
    <div class="market-heads">
      <div class="mh mh1"><h2>${nClinics} clinics compete for them.</h2>
        <p class="sub-s">Every dot is a dermatology clinic in Guntur, placed by real patient demand.</p></div>
      <div class="mh mh2"><h2>${nInvisible} are invisible online.</h2>
        <p class="sub-s">No website. No search presence. Patients can't find them — so they choose someone else.</p></div>
    </div>
    <div class="stage-wrap">
      <div class="stage" id="stage">
        <div class="gapline" id="gapline"><span class="gl-label">the visibility line</span></div>
      </div>
      <div class="ruler" style="color:var(--ink)"></div>
      <div style="display:flex; justify-content:space-between; margin-top:6px">
        <span class="micro-label">lower demand</span><span class="micro-label">higher demand</span>
      </div>
    </div>
  </section>

  <section class="act" id="teasers-act">
    <h2>The invisible are not small clinics.</h2>
    <p class="sub-s">These are real Guntur clinics from our scan — trusted, busy, and unfindable online.
    Names stay private until the examination.</p>
    <div class="teasers">${teaserHTML}</div>
  </section>

  <section class="act" id="turn">
    <h2>The visible few don't even own their visibility.</h2>
    <p class="sub-s">Directory listings rent you a page — and show your competitors right beside your name.</p>
    <div class="turn-rows">
      ${turnRow("Own their visibility", "rank on their own website", ob.owned, "var(--tri-growth-a)")}
      ${turnRow("Rent it", "directories &amp; portals only", ob.borrowed_only, "var(--tri-status-b)")}
      ${turnRow("Invisible", "no web presence at all", ob.invisible, "var(--tri-alert-b)")}
    </div>
  </section>

  <section class="act" id="gate">
    <h2>Where do you stand?</h2>
    <p class="sub-s">Type your clinic's name. We'll tell you if it's in the scan — your numbers stay
    locked until the report.</p>
    <form class="gate-form" id="gate-form">
      <input id="gate-input" type="text" autocomplete="off"
             placeholder="e.g. your clinic's name on Google" aria-label="Find your clinic" />
      <button type="submit">Find my clinic</button>
    </form>
    <div class="gate-card" id="gate-card" aria-live="polite"></div>
  </section>

  <section class="act" id="offer">
    <span class="chip-lime act-kicker">The plans</span>
    <h2 class="offer-lede">You'd never treat before an examination. Neither would we.</h2>
    <div class="offer-grid">
      <div class="plan grain-card grain-card--growth">
        <span class="gc-label" style="align-self:flex-start">The examination</span>
        <h3 style="font:var(--fw-display) var(--fs-title) var(--sans)">Visibility Report</h3>
        <div class="p-price"><span class="dot-num">${inr(P.report)}</span><span class="gc-sub">one-time</span></div>
        <ul style="color:#fff; opacity:.95">
          <li>Your clinic's full visibility diagnosis — rank, score, and every gap</li>
          <li>The market view: all ${nClinics} clinics, benchmarked</li>
          <li>Personal walkthrough, in person or on a call</li>
          <li class="grain-note"><b>Fee fully credited</b> toward a website build within 90 days</li>
        </ul>
        <div class="p-ctas" id="cta-report"></div>
      </div>
      <div class="plan plan-surface">
        <span class="micro-label">The follow-up</span>
        <h3 style="font:var(--fw-display) var(--fs-title) var(--sans)">Visibility Monitoring</h3>
        <div class="p-price"><span class="dot-num">${inr(P.monitor_yr)}</span><span class="p-per">/ year</span></div>
        <p class="p-per">or ${inr(P.monitor_qtr)} per quarter</p>
        <ul>
          <li>Quarterly re-examination of your standing</li>
          <li>Rank &amp; review movement alerts on WhatsApp</li>
          <li>Updated report every quarter</li>
          <li>Social-media analysis — ships to all subscribers</li>
        </ul>
        <div class="p-ctas" id="cta-monitor"></div>
      </div>
      <div class="plan grain-card grain-card--status">
        <span class="gc-label" style="align-self:flex-start">The treatment</span>
        <h3 style="font:var(--fw-display) var(--fs-title) var(--sans)">Website + Visibility Build</h3>
        <div class="p-price"><span class="gc-sub">from</span><span class="dot-num">${inr(P.build_from)}</span></div>
        <ul style="color:#fff; opacity:.95">
          <li>A website that ranks for your own name — and beyond</li>
          <li>Google Business Profile, reviews, and search presence, done right</li>
          <li>Limited slots each quarter — we build exclusively, first come first served</li>
          <li class="grain-note">Optional growth retainer ${inr(P.retainer_mo)}/mo</li>
        </ul>
        <div class="p-ctas" id="cta-build"></div>
      </div>
    </div>
  </section>

  <footer class="site-foot">
    <span>Built from ${nQueries} real Guntur search results and public Google data · ${esc((D.generated_at || "").slice(0, 10))}</span>
    <span>Derma Intel is a Trinade product · no clinic named publicly until they choose to be</span>
  </footer>`;

  /* ---------- CTAs (fallback chain) ---------- */
  const msgReport = "Namaste Trinade! I'd like the Derma Intel Visibility Report for my clinic.";
  const msgMonitor = "Namaste Trinade! I'd like Visibility Monitoring for my clinic.";
  const msgBuild = "Namaste Trinade! I'm interested in a website build for my clinic (Derma Intel).";
  document.getElementById("cta-report").innerHTML =
    A(payHref(P.rzp_report, msgReport), `Get your report — ${inr(P.report)}`, "btn-lime") +
    (P.whatsapp ? A({ href: waLink(msgReport), ext: true }, "Book the walkthrough", "btn-ghost") : "");
  document.getElementById("cta-monitor").innerHTML =
    A(payHref(P.rzp_monitor_yr, msgMonitor), "Start monitoring", "btn-ink");
  document.getElementById("cta-build").innerHTML =
    A({ href: "build.html", ext: false }, "Request a consultation", "btn-lime") +
    (P.whatsapp ? A({ href: waLink(msgBuild), ext: true }, "WhatsApp us", "btn-ghost") : "");

  /* ---------- act 1: ticker + counter ---------- */
  const queries = (D.queries && D.queries.length ? D.queries : ["dermatologist in guntur"]);
  const tickerEl = document.getElementById("ticker-q");
  if (reduced || !hasGsap) {
    tickerEl.textContent = queries[0];
  } else {
    let qi = 0;
    function typeNext() {
      const q = queries[qi % queries.length]; qi++;
      const o = { n: 0 };
      gsap.to(o, {
        n: q.length, duration: Math.min(1.6, q.length * 0.045), ease: "none",
        onUpdate: () => { tickerEl.textContent = q.slice(0, Math.round(o.n)); },
        onComplete: () => gsap.delayedCall(1.4, () =>
          gsap.to(o, { n: 0, duration: 0.3, ease: "none",
            onUpdate: () => { tickerEl.textContent = q.slice(0, Math.round(o.n)); },
            onComplete: typeNext })),
      });
    }
    typeNext();
  }
  const hookN = document.getElementById("hook-n");
  if (reduced || !hasGsap) hookN.textContent = String(nQueries);
  else ScrollTrigger.create({ trigger: "#top", start: "top 70%", once: true,
                              onEnter: () => countUp(hookN, nQueries, 1400) });

  /* ---------- act 2/3: the swarm ---------- */
  const stage = document.getElementById("stage");
  const bees = (D.beeswarm || []).map((b) => {
    const el = document.createElement("div");
    el.className = "bee" + (b.inv ? " inv" : "");
    el.style.left = b.x + "%";
    el.style.top = `calc(38% + ${b.y * 1.6}px)`;
    stage.appendChild(el);
    return { el, b };
  });
  const gapline = document.getElementById("gapline");

  if (reduced || !hasGsap) {
    // static final state: split already applied
    gapline.style.transform = "scaleX(1)";
    bees.forEach(({ el, b }) => {
      if (b.inv) { el.style.top = "82%"; el.classList.add("low"); }
    });
    document.querySelector(".mh1").style.opacity = "0";
    document.querySelector(".mh2").style.opacity = "1";
  } else {
    gsap.set(bees.map((x) => x.el), { scale: 0, opacity: 0 });
    const tl = gsap.timeline({
      scrollTrigger: { trigger: "#market", start: "top top", end: "+=1800", scrub: 0.6, pin: true },
    });
    tl.to(bees.map((x) => x.el), {
      scale: 1, opacity: 0.28, stagger: { each: 0.02, from: "random" },
      ease: "power2.out", duration: 1,
    })
      .to({}, { duration: 0.4 })                                   // hold: read the swarm
      .to(gapline, { scaleX: 1, duration: 0.5, ease: "power2.inOut" })
      .to(bees.filter((x) => x.b.inv).map((x) => x.el), {
        top: "82%", backgroundColor: "#EE6D96", opacity: 0.85,
        stagger: 0.015, duration: 0.9, ease: "power2.inOut",
      }, "<0.2")
      .to(".mh1", { opacity: 0, y: -14, duration: 0.35 }, "<0.1")
      .to(".mh2", { opacity: 1, y: 0, duration: 0.35 }, "<0.15")
      .to({}, { duration: 0.4 });                                  // hold: read the split
  }

  /* ---------- act 4: bars ---------- */
  document.querySelectorAll(".trow").forEach((row) => {
    const bar = row.querySelector(".tr-bar");
    const w = Math.max(parseFloat(bar.dataset.w) || 0, 0.04);
    if (reduced || !hasGsap) { bar.style.transform = `scaleX(${w})`; return; }
    gsap.set(bar, { scaleX: 0 });
    ScrollTrigger.create({
      trigger: row, start: "top 78%", once: true,
      onEnter: () => gsap.to(bar, { scaleX: w, duration: 0.52, ease: "power3.out" }),
    });
  });

  /* ---------- act 5: the gate ---------- */
  const gateCard = document.getElementById("gate-card");
  function renderGate(match, typed) {
    const wa = waLink(`Namaste Trinade! I'd like the Derma Intel Visibility Report for "${typed}".`);
    if (!match) {
      gateCard.innerHTML = `
        <div class="g-found">We map ${nClinics} Guntur clinics — yours may be listed differently.</div>
        <p class="sub-s">Try the exact name from your Google listing${P.whatsapp ? ", or tell us directly:" : "."}</p>
        ${P.whatsapp ? `<div class="gate-ctas">${A({ href: wa, ext: true }, "Ask on WhatsApp", "btn-ghost")}</div>` : ""}`;
    } else {
      const inv = match.inv
        ? `You're one of the <b>${nInvisible} with no web presence at all</b> — patients searching those ${nQueries} queries can't find you.`
        : `You're findable — but your standing vs the other ${nClinics - 1} clinics is what the report shows.`;
      gateCard.innerHTML = `
        <div class="g-found">✓ We found ${esc(typed)}.</div>
        <p class="sub-s" style="margin:0">Visibility standing: <b>${esc(match.bucket)}</b> of ${nClinics}. ${inv}</p>
        <div class="g-score"><span class="dot-num">87</span><div class="g-lock">🔒</div></div>
        <span class="micro-label">your exact score unlocks with the examination</span>
        <div class="gate-ctas">
          ${A(payHref(P.rzp_report, `Namaste Trinade! I'd like the Visibility Report for "${typed}".`), `Get your report — ${inr(P.report)}`, "btn-lime")}
          ${P.whatsapp ? A({ href: wa, ext: true }, "Book the walkthrough", "btn-ghost") : ""}
        </div>`;
    }
    gateCard.classList.add("show");
    if (typeof liquidGlass === "function") {
      try { liquidGlass(gateCard, { scale: -70, chroma: 4 }); } catch (e) { /* fallback stays */ }
    }
    if (hasGsap && !reduced) gsap.from(gateCard, { y: 24, opacity: 0, duration: 0.52, ease: "power3.out" });
  }

  document.getElementById("gate-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const typed = document.getElementById("gate-input").value.trim();
    if (!typed) return;
    const full = fnv1a(normFull(typed) + "{{SALT}}");
    const toks = tokens(typed).map((t) => fnv1a(t + "{{SALT}}"));
    let best = null, bestScore = 0;
    for (const e of D.lookup || []) {
      if (e.h === full) { best = e; bestScore = 1; break; }
      const hits = (e.t || []).filter((h) => toks.includes(h)).length;
      const score = hits / Math.max(e.t.length, 1);
      if (score > bestScore) { bestScore = score; best = e; }
    }
    renderGate(bestScore >= 0.5 ? best : null, typed);
  });

  /* ---------- reveals ---------- */
  if (hasGsap && !reduced) {
    document.querySelectorAll(".act h2, .teasers, .offer-grid, .gate-form").forEach((el) => {
      gsap.from(el, {
        y: 26, opacity: 0, duration: 0.52, ease: "power3.out",
        scrollTrigger: { trigger: el, start: "top 82%", once: true },
      });
    });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => ScrollTrigger.refresh());
  }
})();
