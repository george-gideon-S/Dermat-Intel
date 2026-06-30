/* ============================================================================
   Derma Intel — story  ·  the 7-act scroll narrative (hook → Search Tunnel →
   proof → market → the turn → ₹1500 gate → tabs). Reads window.DI.data.
   Increment A: structure + working paywall. initMotion() (GSAP scrub + tunnel)
   is layered in Increment B; reduced-motion always gets the static narrative.
   ============================================================================ */
(function () {
  "use strict";
  const DI = window.DI || {};
  const D = DI.data || {};
  const CL = D.clinics || [];
  const MK = D.market || {};
  const K = D.kpis || {};
  const QN = K.queries || 80;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const PROOF = (f) => "proof/" + encodeURIComponent(f || "");

  const TOTAL = MK.total || CL.length;
  const INVIS = MK.zero_web_presence != null ? MK.zero_web_presence : Math.max(0, Math.round(TOTAL * 0.44));
  const OWN = MK.own_site != null ? MK.own_site : 0;
  const VISIBLE = Math.max(1, TOTAL - INVIS);
  const SAMPLE = CL.find((c) => c.proof && c.proof.screenshot) || null;
  const PRICE = "₹1500"; // ₹1500

  // tunnel ring data: names spread across rings; ~VISIBLE lit, rest dark
  function tunnelChips() {
    const names = CL.map((c) => c.display_name || c.name).slice(0, 22);
    const litSet = new Set();
    // light the highest-visibility clinics
    CL.slice().sort((a, b) => (b.visibility || 0) - (a.visibility || 0)).slice(0, VISIBLE).forEach((c) => litSet.add(c.display_name || c.name));
    return names.map((n) => ({ n, lit: litSet.has(n) }));
  }

  function actHook() {
    return `<section class="act act-hook" data-act="hook">
      <div class="act-in center">
        <span class="kicker">Trinade · Derma Intel</span>
        <h1 class="story-h1">Every day, patients in Guntur<br>open Google and search.</h1>
        <div class="searchbar"><span class="sb-ic">⌕</span><span class="sb-text" id="hook-type"></span><span class="sb-caret"></span></div>
        <p class="story-sub">The question is simple — and brutal: <b>do they find you?</b></p>
        <div class="scrollcue" aria-hidden="true"><span></span>scroll</div>
      </div>
    </section>`;
  }

  function actTunnel() {
    const chips = tunnelChips();
    const rings = 6;
    let frames = "";
    for (let i = 0; i < rings; i++) {
      const slice = chips.filter((_, j) => j % rings === i).slice(0, 4);
      const chipsHTML = slice.map((c) => `<span class="t-chip ${c.lit ? "lit" : "dark"}">${esc(c.n)}</span>`).join("");
      frames += `<div class="ring" style="--i:${i}">${chipsHTML}</div>`;
    }
    return `<section class="act act-tunnel" data-act="tunnel">
      <div class="tunnel" id="tunnel">${frames}<div class="ring core"></div></div>
      <div class="tunnel-cap">
        <div class="t-counter"><b id="t-count">${TOTAL}</b> clinics surface for these searches —
          <b class="warn" id="t-invis">${INVIS}</b> are <span class="warn">invisible in Google web search.</span></div>
        <p class="story-sub small">Most don't rank their own site. A few own the page. The rest? Patients never see them.</p>
      </div>
    </section>`;
  }

  function actProof() {
    if (!SAMPLE) return "";
    const q = SAMPLE.proof.query || "best dermatologist in Guntur";
    return `<section class="act act-proof" data-act="proof">
      <div class="act-in">
        <span class="kicker">The proof · what patients actually see</span>
        <h2 class="story-h2">This is the page. <span class="hl">Is your clinic on it?</span></h2>
        <figure class="proof-frame"><img src="${PROOF(SAMPLE.proof.screenshot)}" alt="Google results for ${esc(q)}" loading="lazy"><span class="proof-sweep"></span></figure>
        <p class="story-sub">A real Google result for <b>"${esc(q)}"</b>. Every clinic not on it is invisible at the exact moment a patient is choosing.</p>
      </div>
    </section>`;
  }

  function actMarket() {
    const cats = (D.categories || []).slice().sort((a, b) => (b.count || 0) - (a.count || 0)).slice(0, 6);
    const max = Math.max(1, ...cats.map((c) => c.count || 0));
    const HUES = ["#1F6BF0", "#FB5A1E", "#16A64C", "#9B3FEE", "#FFB200", "#ED3A36"];
    const bars = cats.map((c, i) => `<div class="mk-row"><span class="mk-lbl">${esc(c.category)}</span>
      <span class="mk-bar"><i style="width:${Math.round((c.count || 0) / max * 100)}%;background:${HUES[i % HUES.length]}"></i></span></div>`).join("");
    return `<section class="act act-market" data-act="market">
      <div class="act-in">
        <span class="kicker">The market · Guntur dermatology</span>
        <h2 class="story-h2">${TOTAL} clinics. One league table.</h2>
        <div class="mk-grid">
          <div class="mk-stats">
            <div class="mk-stat"><b>${TOTAL}</b><span>clinics mapped</span></div>
            <div class="mk-stat accent"><b>${INVIS}</b><span>invisible online</span></div>
            <div class="mk-stat"><b>${OWN}</b><span>rank their own site</span></div>
          </div>
          <div class="mk-cats"><div class="mk-cap">What patients search for</div>${bars}</div>
        </div>
        <p class="story-sub">Demand is everywhere. Visibility isn't. That gap is the opportunity.</p>
      </div>
    </section>`;
  }

  function actTurn() {
    return `<section class="act act-turn" data-act="turn">
      <div class="act-in center">
        <span class="kicker">And you?</span>
        <h2 class="story-h2 big">But where do <span class="hl">YOU</span> stand?</h2>
        <div class="locked-slot" aria-hidden="true"><div class="ls-blur"></div><div class="ls-lock">🔒</div><div class="ls-rank">Rank&nbsp;#?? of ${TOTAL}</div></div>
        <p class="story-sub">Your clinic's score, your rank, the exact searches you're missing — and your fixes.</p>
      </div>
    </section>`;
  }

  function actGate() {
    return `<section class="act act-gate" data-act="gate" id="gate">
      <div class="gate-card" id="gate-card">
        <span class="kicker">Unlock your report</span>
        <h2 class="story-h2">See where your clinic stands<br><span class="hl">in the Guntur market.</span></h2>
        <ul class="gate-list">
          <li>Your Online Visibility score &amp; rank of ${TOTAL}</li>
          <li>The exact Google searches you're missing</li>
          <li>Your tailored, prioritised fixes</li>
          <li>The full market league &amp; demand map</li>
        </ul>
        <div class="gate-buy">
          <div class="gate-price"><span class="gp-amt">${PRICE}</span><span class="gp-note">one-time · full report + market</span></div>
          <button class="btn-pay" id="pay">Pay ${PRICE} &amp; unlock <span>→</span></button>
        </div>
        <div class="gate-foot"><span class="lock">🔒 secured by <b>Trinade</b></span>
          <button class="gate-restore" id="restore">I've already paid</button></div>
        <p class="gate-demo">Demo build — this simulates the unlock. Real billing is handled by Trinade.</p>
      </div>
      <div class="gate-success" id="gate-success" hidden>
        <div class="gs-check">✓</div><div class="gs-title">You're in.</div>
        <div class="gs-sub">Opening your clinic report…</div>
      </div>
    </section>`;
  }

  function build() {
    const root = document.getElementById("story");
    if (!root) return;
    root.innerHTML = actHook() + actTunnel() + actProof() + actMarket() + actTurn() + actGate();
    typeHook();
    wire();
    if (!DI.reduced) initMotion();
  }

  // hook: type the query (SplitText if present, else manual)
  function typeHook() {
    const el = document.getElementById("hook-type");
    if (!el) return;
    const q = "best dermatologist in Guntur";
    if (DI.reduced) { el.textContent = q; return; }
    let i = 0;
    (function step() { el.textContent = q.slice(0, i++); if (i <= q.length) setTimeout(step, 55); })();
  }

  function wire() {
    const pay = document.getElementById("pay");
    if (pay) pay.addEventListener("click", doPay);
    const restore = document.getElementById("restore");
    if (restore) restore.addEventListener("click", () => { DI.setUnlocked(true); finishUnlock(); });
  }

  function doPay() {
    const card = document.getElementById("gate-card");
    const ok = document.getElementById("gate-success");
    if (!card || !ok) return;
    const btn = document.getElementById("pay");
    btn.disabled = true; btn.classList.add("is-paying"); btn.innerHTML = 'Processing<span class="dots">…</span>';
    setTimeout(() => {
      DI.setUnlocked(true);
      card.hidden = true; ok.hidden = false;
      setTimeout(finishUnlock, DI.reduced ? 200 : 1100);
    }, DI.reduced ? 150 : 1150);
  }

  function finishUnlock() { DI.enterApp("clinic"); }

  function skipToGate() {
    const g = document.getElementById("gate");
    if (g) g.scrollIntoView({ behavior: DI.reduced ? "auto" : "smooth", block: "start" });
  }

  // GSAP scroll choreography. Only runs when motion is allowed (build() guards on DI.reduced).
  function initMotion() {
    if (!window.gsap) return;
    const ST = window.ScrollTrigger;
    try { gsap.registerPlugin(ST, window.SplitText, window.ScrollToPlugin); } catch (e) {}

    // Act 1 — hook headline reveal (words rise in)
    const h1 = document.querySelector(".act-hook .story-h1");
    if (h1 && window.SplitText) {
      try {
        const sp = new SplitText(h1, { type: "words" });
        gsap.from(sp.words, { yPercent: 70, opacity: 0, stagger: 0.06, duration: 0.7, ease: "power3.out", delay: 0.15 });
      } catch (e) {}
    }

    if (!ST) return;

    // Act 2 — the Search Tunnel: pin the act, scrub the camera forward through the rings
    const tunnel = document.querySelector(".act-tunnel");
    const rings = gsap.utils.toArray(".tunnel .ring:not(.core)");
    if (tunnel && rings.length) {
      rings.forEach((r, i) => gsap.set(r, { z: -i * 175, opacity: 1 - i * 0.1, transformOrigin: "50% 50%" }));
      const counter = { v: 0 };
      const elInvis = document.getElementById("t-invis");
      gsap.timeline({ scrollTrigger: { trigger: tunnel, start: "top top", end: "+=200%", pin: true, scrub: 0.6, anticipatePin: 1 } })
        .to(rings, { z: "+=560", ease: "none" }, 0)
        .to(counter, { v: INVIS, ease: "none", snap: { v: 1 }, onUpdate: () => { if (elInvis) elInvis.textContent = Math.round(counter.v); } }, 0)
        .fromTo(".tunnel-cap", { opacity: 0.25, y: 24 }, { opacity: 1, y: 0, ease: "power2.out", duration: 0.4 }, 0.55);
    }

    // Enter-reveals for the remaining acts (fire once on scroll-in)
    const reveal = (sel, vars) => {
      const el = document.querySelector(sel);
      if (!el) return;
      gsap.from(el, Object.assign({ opacity: 0, y: 30, duration: 0.7, ease: "power3.out",
        scrollTrigger: { trigger: el, start: "top 78%", once: true } }, vars || {}));
    };
    reveal(".act-proof .story-h2", { y: 24 });
    reveal(".act-proof .proof-frame");
    reveal(".act-market .story-h2", { y: 24 });
    reveal(".act-turn .locked-slot", { scale: 0.94, y: 20 });
    reveal(".act-gate .gate-card", { y: 36 });

    // market: the category bars draw in
    const bars = gsap.utils.toArray(".mk-bar i");
    if (bars.length) {
      gsap.from(bars, { scaleX: 0, transformOrigin: "0 50%", stagger: 0.08, duration: 0.8, ease: "power3.out",
        scrollTrigger: { trigger: ".act-market", start: "top 60%", once: true } });
    }
    requestAnimationFrame(() => ST.refresh());
  }

  window.DIStory = { skipToGate, onShow: function () {}, rebuild: build };
  build();
})();
