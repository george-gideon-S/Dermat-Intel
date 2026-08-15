/* ── App: panel registry, mount/patch loop, boot ──────────────────────────────
   The core fix over v2. v2 did `root.innerHTML = …` on every tab click, clinic
   change and table sort, disposing and rebuilding all eight charts each time.
   Here both pages exist at once, panels mount ONCE, and afterwards only
   update()/highlight() run. Nothing is ever disposed. */
(function (DI) {
  "use strict";

  const { h, store, bus } = DI;
  const registry = [];
  const mounted = new Map();   // id -> { def, api, host, version }

  /**
   * @param {object} def
   *   id       unique
   *   page     "clinic" | "market"
   *   span     grid columns (1..12)
   *   rows     grid rows
   *   card     render on the Card rung (default true); false = naked on the field
   *   title    panel heading
   *   sub      quiet sub-heading
   *   mount(body, ctx)          build DOM/chart ONCE, return an api object
   *   update(api, ctx)          data or filter changed -> patch in place
   *   highlight(api, key)       hover -> emphasis only, never layout
   *   expand(api, ctx)          optional; presence adds the corner ↗ and wires it
   *   subject   true = also re-render when the selected clinic changes
   */
  function register(def) { registry.push(def); }

  /** Which rung the card sits on. `dark` is the v4 addition: a card that
   *  overlaps the background subject's dark zone. Chosen by ROLE, never by
   *  taste — mixing rungs on one ground is the failure ATLAS-DARK.md §5.2
   *  exists to prevent. */
  function rungClass(def) {
    if (def.card === false) return ".panel--naked";
    return def.rung === "dark" ? ".panel--dark" : ".panel--card";
  }

  /* The seven bento sizes (V0_CARD_INVENTORY.md §1). A v4 card declares the
     NAME and the stylesheet owns what it means at each breakpoint.

     Two measured reasons it has to work that way rather than writing the
     numbers inline, as v3 did:

     1. An inline custom property beats every stylesheet rule, and no media
        query can override it. A card carrying style="--span: 3" keeps --span:3
        at every width, so the reflow table simply could not be expressed.
     2. --span cannot even tell the sizes apart. stat and tall are both 3
        columns, half and panel both 6, band and hero both 12 — and the reflow
        sends stat to 2 columns while tall goes to 4. The name has to survive
        into the DOM or that rule is unwriteable.

     Legacy v3 panels keep the inline vars byte-for-byte, so the two systems
     coexist through a page-by-page cutover. */
  const SIZES = ["stat", "wide", "half", "tall", "panel", "band", "hero"];

  function panelShell(def) {
    const sized = SIZES.indexOf(def.size) >= 0;
    if (def.size && !sized) console.warn(`[panel:${def.id}] unknown size ${def.size}`);
    const el = h(`section.panel${rungClass(def)}`, {
      style: sized ? null : { "--span": def.span || 12, "--rows": def.rows || 1 },
      data: {
        panel: def.id,
        size: sized ? def.size : null,
        // Dense censuses go full-width on a phone so their dot pitch stays
        // legible. It cannot be derived from the size — two of the three are
        // `stat` and one is `half` — so it is its own flag.
        dense: def.dense ? "1" : null,
      },
      "aria-label": def.title || def.id,
    });
    if (def.title) {
      const head = h("div.panel__head", h("h2", { text: def.title }));
      if (def.sub) head.append(h("span.sub", { text: def.sub }));
      el.append(head);
    }
    const body = h("div.panel__body.grow");
    el.append(body);
    // The corner mark appears only where a drawer actually opens, so it always
    // means "there is more" rather than decorating the card.
    let expand = null;
    if (typeof def.expand === "function") {
      expand = h("button.expand", {
        type: "button", text: "↗",
        "aria-label": `Expand ${def.title || def.id}`,
      });
      el.append(expand);
    }
    return { el, body, expand };
  }

  function mountPage(page) {
    const root = document.querySelector(`.canvas[data-page="${page}"]`);
    if (!root || root.dataset.mounted === "1") return;
    const ctx = context();
    for (const def of registry.filter((d) => d.page === page)) {
      const { el, body, expand } = panelShell(def);
      root.append(el);
      let api = null;
      try {
        api = def.mount ? def.mount(body, ctx) : null;
      } catch (err) {
        console.error(`[panel:${def.id}] mount failed`, err);
        body.append(h("div.panel__note", { text: "This panel could not be drawn." }));
      }
      // Wired after mount so the handler receives the api the panel returned.
      if (expand) {
        expand.addEventListener("click", () => {
          try { def.expand(api, context()); } catch (err) { console.error(`[panel:${def.id}] expand failed`, err); }
        });
      }
      mounted.set(def.id, { def, api, host: el, body, version: ctx.version });
    }
    root.dataset.mounted = "1";
  }

  function context() {
    const v = store.view();
    return { ...v, D: DI.D };
  }

  /** Patch every mounted panel on the visible page whose version is stale. */
  function updateAll(opts = {}) {
    const ctx = context();
    for (const rec of mounted.values()) {
      if (rec.def.page !== store.state.page) { rec.version = -1; continue; }
      if (!opts.force && rec.version === ctx.version) continue;
      try {
        if (rec.def.update) rec.def.update(rec.api, ctx);
        rec.version = ctx.version;
      } catch (err) {
        console.error(`[panel:${rec.def.id}] update failed`, err);
      }
    }
  }

  function go(page) {
    if (page === store.state.page) return;
    store.setPage(page);
    document.querySelectorAll(".canvas").forEach((el) => {
      el.hidden = el.dataset.page !== page;
    });
    mountPage(page);
    bus.emit("page", { page });
    // A chart initialised inside a hidden section measured 0; tell it the truth
    // now that it is visible.
    updateAll();
    requestAnimationFrame(() => DI.charts.resizeAll());
  }

  /* ── Drawer: one overlay system for every drill-in ─────────────────────── */
  let lastFocus = null;
  function openDrawer(title, buildBody) {
    const drawer = document.getElementById("drawer");
    const scrim = document.getElementById("drawer-scrim");
    lastFocus = document.activeElement;
    drawer.textContent = "";
    drawer.append(h("div.drawer__head",
      h("h2", { text: title }),
      h("button.drawer__close", { type: "button", text: "Close ×",
                                  "aria-label": "Close details", onclick: closeDrawer })));
    const body = h("div.stack");
    drawer.append(body);
    try { buildBody(body); } catch (err) { console.error("[drawer]", err); }
    drawer.hidden = false;
    scrim.hidden = false;
    drawer.focus();
  }

  function closeDrawer() {
    document.getElementById("drawer").hidden = true;
    document.getElementById("drawer-scrim").hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function boot() {
    if (!DI.CL.length) {
      document.getElementById("canvas").append(
        h("div.panel__note", { text: "No clinic data in this build." }));
      return;
    }

    DI.topbar.build(document.getElementById("topbar"),
                    document.getElementById("titleblock"),
                    document.getElementById("shellfoot"));
    mountPage("clinic");

    // The picker gates the dashboard on first visit only. It runs AFTER the
    // mount so entering is instant and the charts already exist; they are
    // resized on the way out, because a chart built inside a hidden container
    // measured 0x0.
    DI.picker.start();

    // Hover: emphasis only. Never a re-render, never a setOption.
    bus.on("hover", ({ key }) => {
      for (const rec of mounted.values()) {
        if (rec.def.page !== store.state.page || !rec.def.highlight) continue;
        try { rec.def.highlight(rec.api, key); } catch (_) { /* non-fatal */ }
      }
    });

    // Select changes the subject, and far more panels draw it than declare
    // `subject: true` — six market panels mark the selected clinic (the
    // opportunity ring, the league terminal dot, the butterfly, the ad-shelf row,
    // the map dot, the table row) without opting in, so they kept painting the
    // previous subject until something else forced a repaint. An opt-in flag was
    // the wrong mechanism: a full patch of the visible page measures ~27ms, which
    // is cheaper than the class of bug it prevents.
    bus.on("select", () => updateAll({ force: true }));

    // Filter: one memoised recompute, then patch everything on the page.
    bus.on("filter", () => updateAll({ force: true }));

    document.getElementById("drawer-scrim").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !document.getElementById("drawer").hidden) closeDrawer();
    });

    // The verifier waits on this flag rather than a fixed timeout, so a slow
    // font load can never produce a blank screenshot.
    document.fonts.ready.then(() => {
      DI.charts.resizeAll();
      document.body.dataset.diReady = "1";
    });
  }

  DI.app = { register, go, boot, updateAll, openDrawer, closeDrawer, mounted, context };
  DI.boot = boot;
})(window.DI);
