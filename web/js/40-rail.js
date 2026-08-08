/* ── The console rail ─────────────────────────────────────────────────────────
   Wordmark, big-type page switch, the branded clinic selector, the market
   facets, and the data-vintage footer. Built once; only the pressed states and
   the selector label change afterwards. */
(function (DI) {
  "use strict";

  const { h, store, bus, D, CL } = DI;

  /* ── Branded combobox ───────────────────────────────────────────────────────
     A native <select> is banned by the design laws (the verifier counts them),
     and it could not carry the value pills anyway. This is the minimum honest
     combobox: roles, keyboard, type-to-filter. */
  function combobox() {
    let open = false, active = 0, matches = CL.slice();

    const label = h("span.who");
    const rank = h("span.rank");
    const btn = h("button.combo__btn", {
      type: "button", role: "combobox", "aria-expanded": "false",
      "aria-haspopup": "listbox", "aria-label": "Choose a clinic",
    }, label, rank, h("span.caret", { text: "▾", "aria-hidden": "true" }));

    const search = h("input.combo__search", {
      type: "text", placeholder: "Type to find a clinic…",
      "aria-label": "Filter clinics",
    });
    const list = h("div.combo__list", { role: "listbox" });
    const pop = h("div.combo__pop", { hidden: true }, search, list);
    const root = h("div.combo", btn, pop);

    function paint() {
      const subject = store.view().subject;
      label.textContent = subject ? subject.display_name : "—";
      rank.textContent = subject ? `#${subject.visibility_rank}` : "";
    }

    function renderList() {
      list.textContent = "";
      const subject = store.view().subject;
      matches.forEach((c, i) => {
        list.append(h("button.combo__opt", {
          type: "button", role: "option",
          "aria-selected": String(!!subject && c.key === subject.key),
          class: "combo__opt" + (i === active ? " is-active" : ""),
          onclick: () => choose(c.key),
        },
          h("span.who", { text: c.display_name }),
          h("span.v", { text: String(c.visibility) })));
      });
      if (!matches.length) {
        list.append(h("div.combo__opt", { text: "No clinic matches that name." }));
      }
    }

    function filterBy(q) {
      const needle = q.trim().toLowerCase();
      matches = needle
        ? CL.filter((c) => (c.display_name + " " + c.name).toLowerCase().includes(needle))
        : CL.slice();
      active = 0;
      renderList();
    }

    function setOpen(next) {
      open = next;
      pop.hidden = !next;
      btn.setAttribute("aria-expanded", String(next));
      if (next) { search.value = ""; filterBy(""); search.focus(); }
    }

    function choose(key) {
      if (store.select(key)) bus.emit("select", { key });
      paint();
      setOpen(false);
      btn.focus();
    }

    btn.addEventListener("click", () => setOpen(!open));
    search.addEventListener("input", () => filterBy(search.value));
    search.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { active = Math.min(active + 1, matches.length - 1); renderList(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(active - 1, 0); renderList(); e.preventDefault(); }
      else if (e.key === "Enter" && matches[active]) { choose(matches[active].key); e.preventDefault(); }
      else if (e.key === "Escape") { setOpen(false); btn.focus(); }
    });
    document.addEventListener("pointerdown", (e) => {
      if (open && !root.contains(e.target)) setOpen(false);
    });

    paint();
    bus.on("select", paint);
    return root;
  }

  /* ── Facet rows ─────────────────────────────────────────────────────────── */
  function facetRow(labelText, count, pressed, onToggle, dotVar) {
    return h("button.rrow", {
      type: "button", "aria-pressed": String(!!pressed), onclick: onToggle,
    },
      dotVar ? h("span.dot", { style: { background: `var(${dotVar})` } }) : null,
      h("span.lbl", { text: labelText }),
      h("span.n", { text: String(count) }));
  }

  function build(rail) {
    const facets = D.facets || {};
    rail.textContent = "";

    rail.append(h("div.wordmark", "derma intel", h("span.city", { text: "guntur" })));

    // The big-type switch — the reference's Data/Records pair, not a tab bar.
    const sw = h("nav.switch", { "aria-label": "Views" });
    [["clinic", "Your Clinic"], ["market", "The Market"]].forEach(([page, text]) => {
      sw.append(h("button", {
        type: "button", text, data: { page },
        "aria-current": store.state.page === page ? "page" : null,
        onclick: () => DI.app.go(page),
      }));
    });
    rail.append(sw);

    rail.append(combobox());

    const groups = [
      ["Where they stand", (facets.band || []).map((r) => ({
        label: r.label, count: r.count, facet: "band", value: r.key,
        dot: `--jewel-${r.key}-core`,
      }))],
      ["Web presence", (facets.presence || []).map((r) => ({
        label: r.label, count: r.count, facet: "presence", value: r.key,
      }))],
      ["Verdict", (facets.verdict || []).map((r) => ({
        label: DI.short(r.label, 30), count: r.count, facet: "verdict", value: r.key,
      }))],
    ];

    for (const [title, rows] of groups) {
      if (!rows.length) continue;
      const g = h("div.rail-group", h("div.rail-title", { text: title }));
      for (const r of rows) {
        g.append(facetRow(r.label, r.count, store.state.filter[r.facet].has(r.value), () => {
          store.toggleFacet(r.facet, r.value);
          bus.emit("filter", {});
        }, r.dot));
      }
      rail.append(g);
    }

    if (facets.ads) {
      rail.append(h("div.rail-group",
        facetRow("Buys Google ads", facets.ads, store.state.filter.ads, () => {
          store.setAds(!store.state.filter.ads);
          bus.emit("filter", {});
        })));
    }

    const clear = h("button.rail-clear", {
      type: "button", text: "× clear filters", hidden: !store.isFiltered(),
      onclick: () => { store.clearFilters(); bus.emit("filter", {}); },
    });
    rail.append(clear);

    // Three datasets, three vintages. The footer states them rather than
    // implying one "as of" date across all of it.
    const v = D.vintages || {};
    rail.append(h("div.rail-foot", { tabindex: "0" },
      h("div", { text: `${D.kpis ? D.kpis.unique_clinics : CL.length} clinics · ${(D.kpis || {}).queries || 0} queries` }),
      h("dl",
        h("dt", { text: "Google Maps scrape" }), h("dd", { text: v.maps || "—" }),
        h("dt", { text: "Search results read" }), h("dd", { text: v.serp || "—" }),
        h("dt", { text: "Report built" }), h("dd", { text: v.build || "—" }))));

    // The calibration swatch strip. It must render real pixels for the probe
    // harness to sample, so it is visible but tiny and aria-hidden.
    const strip = h("div.probestrip", { "data-verify": "probestrip", "aria-hidden": "true" });
    ["--sf-field", "--ink-1", "--ink-3", "--sf-flatCard", "--sf-flatInner",
     "--accent-lime", "--jewel-clear-core", "--jewel-index-core"]
      .forEach((tok) => strip.append(h("i", { style: { background: `var(${tok})` }, title: tok })));
    rail.append(strip);

    // Keep pressed states and the clear button honest after any filter change.
    bus.on("filter", () => {
      clear.hidden = !store.isFiltered();
      rail.querySelectorAll(".rrow").forEach((el) => { /* rebuilt below */ });
      repaintFacets(rail);
    });
    bus.on("page", () => {
      sw.querySelectorAll("button").forEach((b) => {
        if (b.dataset.page === store.state.page) b.setAttribute("aria-current", "page");
        else b.removeAttribute("aria-current");
      });
    });
  }

  /** Re-derive pressed state from the store without rebuilding the rail. */
  function repaintFacets(rail) {
    const f = store.state.filter;
    const all = [...(D.facets.band || []).map((r) => ["band", r.key]),
                 ...(D.facets.presence || []).map((r) => ["presence", r.key]),
                 ...(D.facets.verdict || []).map((r) => ["verdict", r.key])];
    const rows = rail.querySelectorAll(".rail-group .rrow");
    all.forEach(([facet, value], i) => {
      const el = rows[i];
      if (el) el.setAttribute("aria-pressed", String(f[facet].has(value)));
    });
    const adsRow = rows[all.length];
    if (adsRow) adsRow.setAttribute("aria-pressed", String(f.ads));
  }

  DI.rail = { build };
})(window.DI);
