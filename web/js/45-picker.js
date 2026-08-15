/* ── The clinic picker ────────────────────────────────────────────────────────
   v4 killed the rail's 250px dropdown, where a name like
   "Dr.Keerthi Sidda's Skin,Hair& Laser clinic" had nowhere to go. Choosing which
   of 34 clinics you are is a first-run decision that deserves the whole canvas,
   not a truncated combobox.

   It gates the dashboard on first visit only. The choice is remembered, and the
   top bar keeps a way back in.

   STORAGE — the key is namespaced deliberately. Chromium treats every `file://`
   document as ONE shared origin, so an unprefixed key like "subject" would be
   read and written by any other local HTML file the user has ever opened,
   including earlier builds of this very report. Reads and writes are wrapped:
   localStorage throws outright when a browser is configured to block storage on
   file://, and a thrown getItem must not take the dashboard down with it. */
(function (DI) {
  "use strict";

  const { h, store, bus, CL } = DI;
  const KEY = "derma-intel.v4.subject";

  function remembered() {
    try { return window.localStorage.getItem(KEY); } catch (_) { return null; }
  }
  function remember(key) {
    try { window.localStorage.setItem(KEY, key); } catch (_) { /* storage blocked */ }
  }

  /* The surfaces the picker covers while it is up. Kept in one place so opening
     and closing can never disagree about what to hide. */
  function chrome() {
    return [document.getElementById("titleblock"),
            document.getElementById("canvas"),
            document.getElementById("shellfoot")].filter(Boolean);
  }

  /** One clinic card. Identity plus the facts that help you recognise yourself —
   *  never the diagnosis, which is what the report you are about to open is for. */
  function card(c, onPick) {
    const band = store.bandOf(c.visibility);
    return h("button.pk__card", {
      type: "button",
      data: { clinic: c.key },
      "aria-label": `${c.display_name}, visibility ${c.visibility} of 100, ranked ${c.visibility_rank} of ${CL.length}`,
      onclick: () => onPick(c.key),
    },
      h("span.pk__name", { text: c.display_name }),
      h("span.pk__facts",
        h("span.pk__vis", { text: String(c.visibility) }),
        h("span.pk__dot", { style: { background: `var(--jewel-${band}-core)` }, "aria-hidden": "true" }),
        h("span.pk__unit", { text: "visibility" }),
        h("span.pk__rank", { text: `#${c.visibility_rank}` })),
      h("span.pk__meta", {
        text: `${DI.num(c.reviews || 0, 0)} reviews · ${c.has_website ? "has a website" : "no website"}`,
      }));
  }

  function build(root, onEnter) {
    root.textContent = "";

    const grid = h("div.pk__grid");
    const empty = h("p.pk__empty", {
      text: "No clinic matches that name.", hidden: true,
    });
    const count = h("p.pk__count");
    let matches = CL.slice();

    function pick(key) {
      if (store.select(key)) bus.emit("select", { key });
      remember(key);
      close();
      if (onEnter) onEnter();
    }

    function render() {
      grid.textContent = "";
      matches.forEach((c) => grid.append(card(c, pick)));
      empty.hidden = matches.length > 0;
      count.textContent = matches.length === CL.length
        ? `${CL.length} clinics in Guntur`
        : `${matches.length} of ${CL.length} clinics`;
    }

    const search = h("input.pk__search", {
      type: "text",
      placeholder: "Search for your clinic…",
      "aria-label": "Search clinics by name",
      autocomplete: "off",
    });
    search.addEventListener("input", () => {
      const needle = search.value.trim().toLowerCase();
      matches = needle
        ? CL.filter((c) => (c.display_name + " " + c.name).toLowerCase().includes(needle))
        : CL.slice();
      render();
    });
    search.addEventListener("keydown", (e) => {
      // Enter takes the obvious answer when the search has narrowed to one.
      if (e.key === "Enter" && matches.length) { pick(matches[0].key); e.preventDefault(); }
      else if (e.key === "Escape") { search.value = ""; matches = CL.slice(); render(); }
    });

    render();

    root.append(
      h("div.pk__inner",
        h("h1.pk__title", { text: "Which clinic are you?" }),
        h("p.pk__lede", {
          text: "Pick yours to open its report. We read every dermatology clinic in "
              + "Guntur — this only decides which one the dashboard is about.",
        }),
        h("div.pk__searchwrap", search),
        count,
        grid,
        empty));

    return { search };
  }

  let api = null;

  function open() {
    const root = document.getElementById("picker");
    if (!root) return;
    if (!api) api = build(root, () => DI.charts && DI.charts.resizeAll());
    root.hidden = false;
    chrome().forEach((el) => { el.hidden = true; });
    document.body.dataset.picking = "1";
    api.search.focus();
  }

  function close() {
    const root = document.getElementById("picker");
    if (root) root.hidden = true;
    chrome().forEach((el) => { el.hidden = false; });
    delete document.body.dataset.picking;
  }

  /** Called by boot(). Opens the picker only when nothing is remembered; when a
   *  choice exists it becomes the subject and the dashboard opens straight up. */
  function start() {
    const key = remembered();
    if (key && DI.byKey.get(key)) {
      if (store.select(key)) bus.emit("select", { key });
      close();
      return false;
    }
    open();
    return true;
  }

  // Keep the remembered choice honest when the subject changes anywhere else —
  // the combobox, a league row, a table row, a map pin.
  bus.on("select", ({ key }) => { if (key) remember(key); });

  DI.picker = { start, open, close, KEY };
})(window.DI);
