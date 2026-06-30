/* ============================================================================
   Derma Intel — shell  ·  shared state, top-bar chrome, nav routing, unlock state.
   Globals: window.DI (state + API). story.js sets window.DIStory; app.js sets DI.renderApp.
   Script order at runtime: gsap → data → shell → story → app → DI.boot().
   ============================================================================ */
(function () {
  "use strict";
  const D = window.__DATA__ || {};
  const reduced = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  const LS = "derma_unlocked";

  const DI = (window.DI = {
    data: D,
    reduced,
    state: "story",     // "story" | "app"
    view: "clinic",     // active tab when state === "app"
    els: {},
    isUnlocked() { try { return localStorage.getItem(LS) === "1"; } catch (e) { return false; } },
    setUnlocked(v) {
      try { v ? localStorage.setItem(LS, "1") : localStorage.removeItem(LS); } catch (e) {}
      DI.renderChrome();
    },
  });

  function chromeHTML() {
    const unlocked = DI.isUnlocked();
    const inApp = DI.state === "app";
    const right = inApp
      ? `<nav class="pillnav" aria-label="Sections">
           <button class="pn ${DI.view === "clinic" ? "on" : ""}" data-nav="clinic">Your Clinic</button>
           <button class="pn ${DI.view === "market" ? "on" : ""}" data-nav="market">All Clinics</button>
           <button class="pn ghost" data-nav="story">Story</button>
         </nav>`
      : (unlocked
          ? `<button class="pn solid" data-nav="app">Enter dashboard →</button>`
          : `<button class="bar-skip" data-nav="skip">Skip intro</button>`);
    return `<div class="bar-in">
        <a class="bar-brand" href="#" data-nav="story">Trinade<span class="sep">·</span>Derma&nbsp;Intel<span class="dot">.</span></a>
        <div class="bar-right">${right}</div>
      </div>
      <div class="bar-rail"><i id="bar-rail-fill"></i></div>`;
  }

  DI.renderChrome = function () {
    let c = document.getElementById("chrome");
    if (!c) { c = document.createElement("header"); c.id = "chrome"; c.className = "topbar"; document.body.prepend(c); }
    c.innerHTML = chromeHTML();
    c.querySelectorAll("[data-nav]").forEach((b) =>
      b.addEventListener("click", (e) => { e.preventDefault(); route(b.dataset.nav); }));
    DI.els.railFill = document.getElementById("bar-rail-fill");
  };

  function route(to) {
    if (to === "story") return DI.showStory();
    if (to === "skip") return window.DIStory && DIStory.skipToGate ? DIStory.skipToGate() : DI.showStory();
    if (to === "app") return DI.enterApp(DI.view);
    if (to === "clinic" || to === "market") {
      if (!DI.isUnlocked()) return window.DIStory && DIStory.skipToGate ? DIStory.skipToGate() : null;
      return DI.enterApp(to);
    }
  }

  DI.showStory = function () {
    DI.state = "story";
    const app = document.getElementById("app"), story = document.getElementById("story");
    if (app) app.hidden = true;
    if (story) story.hidden = false;
    document.body.classList.remove("in-app");
    DI.renderChrome();
    if (window.DIStory && DIStory.onShow) DIStory.onShow();
    window.scrollTo(0, 0);
    requestAnimationFrame(function () { if (window.ScrollTrigger) ScrollTrigger.refresh(); });
  };

  DI.enterApp = function (view) {
    if (!DI.isUnlocked()) return window.DIStory && DIStory.skipToGate ? DIStory.skipToGate() : null;
    DI.state = "app";
    DI.view = view || DI.view;
    const app = document.getElementById("app"), story = document.getElementById("story");
    if (story) story.hidden = true;
    if (app) app.hidden = false;
    document.body.classList.add("in-app");
    DI.renderChrome();
    if (DI.renderApp) DI.renderApp(DI.view);
    requestAnimationFrame(function () { window.scrollTo(0, 0); if (window.ScrollTrigger) ScrollTrigger.refresh(); });
  };

  // scroll-progress rail (cheap; always on, independent of GSAP)
  function onScroll() {
    const f = DI.els.railFill;
    if (!f || DI.state === "app") return;
    const h = document.documentElement;
    const max = h.scrollHeight - h.clientHeight;
    f.style.transform = "scaleX(" + (max > 0 ? Math.min(1, h.scrollTop / max) : 0) + ")";
  }
  window.addEventListener("scroll", onScroll, { passive: true });

  DI.boot = function () {
    if (!D || !(D.clinics || []).length) {
      document.body.innerHTML = '<div style="padding:14vh 8vw;font-family:system-ui">' +
        "<h1>No data yet.</h1><p>Run <code>python run_pipeline.py</code> then <code>python web/build_web.py</code>.</p></div>";
      return;
    }
    DI.renderChrome();
    DI.showStory();
    onScroll();
  };
})();
