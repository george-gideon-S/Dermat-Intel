/* ── The top bar, the editorial title block and the shell footer ──────────────
   v4 replaced the 250px console rail with this. Three things moved and one died:

     · the page switch  -> pills up here (SAME .switch / button[data-page] markup,
                           so every tool that drives the app by those selectors
                           keeps working; only the styling moved)
     · the clinic picker -> the utility cluster (SAME .combo markup, ported
                           verbatim — a native <select> is still banned)
     · the vintages     -> the shell footer
     · the facet rows   -> DELETED. Filters belong on the surface they filter
                           (the map's glass pills, a card header), not in a rail
                           of thirteen rows. The verdict facet is gone entirely:
                           five free-text rows made a poor facet, and the verdict
                           now reads as the clinic's subtitle instead.

   The store's facet API is untouched, so nothing downstream had to change. */
(function (DI) {
  "use strict";

  const { h, s, store, bus, D, CL } = DI;

  /* ── Branded combobox ───────────────────────────────────────────────────────
     Ported from the rail unchanged. A native <select> is banned by the design
     laws (the verifier counts them), and it could not carry the value pills
     anyway. This is the minimum honest combobox: roles, keyboard, type-to-filter. */
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

  /* ── Utility icons ──────────────────────────────────────────────────────────
     Drawn, never imported: the app constructs no <img>, and an icon font would
     be a second type system. 18px on a 24 grid at stroke 1.5, per atlas §7. */
  const ICONS = {
    settings: ["M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
               "M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.04 1.56V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 8.9 19.3a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.04H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.56-1.15 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.56V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1.04 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"],
    bell: ["M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9",
           "M13.73 21a2 2 0 0 1-3.46 0"],
    account: ["M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
              "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"],
  };

  function icon(name) {
    return s("svg", {
      viewBox: "0 0 24 24", width: 18, height: 18, fill: "none",
      stroke: "currentColor", "stroke-width": 1.5,
      "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true",
    }, ICONS[name].map((d) => s("path", { d })));
  }

  function utilBtn(name, label) {
    return h("button.ubtn", { type: "button", "aria-label": label, title: label },
      icon(name));
  }

  /* ── The editorial title block ──────────────────────────────────────────────
     Your Clinic leads with the clinic and its verdict — the one-line diagnosis
     ships in the payload and, before v4, was never shown on the clinic's own
     report (it only surfaced truncated as a rail facet label). The Market leads
     with the corpus, and states all three denominators so the 78-vs-80 question
     is answered before it is asked. */
  function paintTitle(el) {
    el.textContent = "";
    const v = store.view();

    if (store.state.page === "clinic") {
      const c = v.subject;
      if (!c) return;
      el.append(
        h("h1.titleblock__display", { text: c.display_name }),
        h("p.titleblock__sub", { text: c.verdict || "" }));
      return;
    }

    const k = D.kpis || {};
    const blocks = ((D.serp || {}).ownership || {}).totals || {};
    const parts = [`${k.unique_clinics || CL.length} clinics`];
    if (k.queries) parts.push(`${k.queries} searches read`);
    if (blocks.blocks && blocks.queries) {
      // Grouped by hand rather than toLocaleString: the verifier's screenshots
      // have to reproduce byte for byte, and locale formatting is not ours to
      // control. The 78 is named explicitly — the blocks come from the captured
      // result pages, not from the 80 searches beside them.
      const grouped = String(blocks.blocks).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      parts.push(`${grouped} blocks across ${blocks.queries} result pages`);
    }
    el.append(
      h("h1.titleblock__display", { text: "The Guntur market" }),
      h("p.titleblock__sub", { text: parts.join(" · ") }));
  }

  /* ── Build ──────────────────────────────────────────────────────────────── */
  function build(bar, title, foot) {
    bar.textContent = "";

    const lead = h("div.topbar__lead",
      h("div.wordmark", "derma intel", h("span.city", { text: "guntur" })));

    // Pills. Same .switch / button[data-page] contract as the rail's big-type
    // switch — only the styling moved, so anything driving the app by those
    // selectors is unaffected.
    const sw = h("nav.switch", { "aria-label": "Views" });
    [["clinic", "Your Clinic"], ["market", "The Market"]].forEach(([page, text]) => {
      sw.append(h("button", {
        type: "button", text, data: { page },
        "aria-current": store.state.page === page ? "page" : null,
        onclick: () => DI.app.go(page),
      }));
    });
    lead.append(sw);

    bar.append(lead, h("div.topbar__utility",
      combobox(),
      utilBtn("settings", "Settings"),
      utilBtn("bell", "Notifications"),
      utilBtn("account", "Account")));

    // Title block, repainted whenever the page or the subject changes.
    paintTitle(title);
    bus.on("select", () => paintTitle(title));

    bus.on("page", () => {
      sw.querySelectorAll("button").forEach((b) => {
        if (b.dataset.page === store.state.page) b.setAttribute("aria-current", "page");
        else b.removeAttribute("aria-current");
      });
      paintTitle(title);
    });

    // ── Footer: three datasets, three vintages, never one "as of" date.
    foot.textContent = "";
    const v = D.vintages || {};
    foot.append(h("dl.vintages",
      h("dt", { text: "Google Maps scrape" }), h("dd", { text: v.maps || "—" }),
      h("dt", { text: "Search results read" }), h("dd", { text: v.serp || "—" }),
      h("dt", { text: "Report built" }), h("dd", { text: v.build || "—" })));

    // The calibration swatch strip. It must render real pixels for the Pillow
    // probe harness to sample, so it is visible but tiny and aria-hidden. It
    // lived in the rail; it lives here now, and the verifier's two census
    // exemptions key off the class, not the location.
    const strip = h("div.probestrip", { "data-verify": "probestrip", "aria-hidden": "true" });
    ["--sf-field", "--ink-1", "--ink-3", "--sf-flatCard", "--sf-flatInner",
     "--accent-lime", "--jewel-clear-core", "--jewel-index-core",
     "--sfDark-flatSurface", "--sfDark-flatNested"]
      .forEach((tok) => strip.append(h("i", { style: { background: `var(${tok})` }, title: tok })));
    foot.append(strip);
  }

  DI.topbar = { build, paintTitle };
})(window.DI);
