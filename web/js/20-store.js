/* ── Store: state + memoised selectors ────────────────────────────────────────
   One integer `version` is the whole cache-invalidation strategy. Panels compare
   the version they last rendered against the current one and no-op when it has
   not moved, which is what keeps a filter round-trip cheap. */
(function (DI) {
  "use strict";

  const D = window.__DATA__ || {};
  const CL = D.clinics || [];
  const byKey = new Map(CL.map((c) => [c.key, c]));

  function emptyFilter() {
    return { verdict: new Set(), presence: new Set(), band: new Set(),
             category: new Set(), ads: false, keys: null };
  }

  const state = {
    page: "clinic",
    selected: CL.length ? CL[0].key : null,
    filter: emptyFilter(),
    version: 0,
  };

  /** Presence grouping — mirrors web/views.py::presence_of exactly. A paid
   *  placement is OWNED (you control the destination); places-only is INVISIBLE
   *  (the local pack is Maps re-surfaced). */
  function presenceOf(c) {
    const w = c.web || {};
    if (w.has_own_site || (w.owned || 0) > 0) return "own";
    if ((w.borrowed || 0) > 0 || (w.platforms || []).length) return "borrowed";
    return "invisible";
  }

  /** Band — mirrors web/views.py::band_of and the jewel state-map thresholds. */
  function bandOf(v) {
    if (v === null || v === undefined) return "alarm";
    if (v <= 20) return "alarm";
    if (v <= 50) return "caution";
    if (v <= 79) return "steady";
    return "clear";
  }

  function passes(c, f) {
    if (f.keys && !f.keys.has(c.key)) return false;
    if (f.verdict.size && !f.verdict.has(c.verdict)) return false;
    if (f.presence.size && !f.presence.has(presenceOf(c))) return false;
    if (f.band.size && !f.band.has(bandOf(c.visibility))) return false;
    if (f.ads && !(c.sponsored > 0)) return false;
    if (f.category.size) {
      const cats = new Set((c.intents || []).map((i) => i.cat));
      let hit = false;
      for (const cat of f.category) if (cats.has(cat)) { hit = true; break; }
      if (!hit) return false;
    }
    return true;
  }

  let cache = null;

  function view() {
    if (cache && cache.version === state.version) return cache;
    const filtered = CL.filter((c) => passes(c, state.filter));
    cache = {
      version: state.version,
      all: CL,
      filtered,
      keys: new Set(filtered.map((c) => c.key)),
      subject: byKey.get(state.selected) || CL[0] || null,
      page: state.page,
      active: isFiltered(),
    };
    return cache;
  }

  function isFiltered() {
    const f = state.filter;
    return !!(f.keys || f.ads || f.verdict.size || f.presence.size ||
              f.band.size || f.category.size);
  }

  function bump() { state.version++; }

  function setPage(page) { state.page = page; }

  function select(key) {
    if (!byKey.has(key) || key === state.selected) return false;
    state.selected = key;
    bump();
    return true;
  }

  /** Toggle one value inside a Set-valued facet. */
  function toggleFacet(facet, value) {
    const set = state.filter[facet];
    if (!(set instanceof Set)) return;
    if (set.has(value)) set.delete(value); else set.add(value);
    bump();
  }

  function setAds(on) { state.filter.ads = !!on; bump(); }

  /** The brush result. Passing null clears just the key-set, leaving facets. */
  function setKeys(keys) {
    state.filter.keys = keys && keys.size ? keys : null;
    bump();
  }

  function clearFilters() {
    state.filter = emptyFilter();
    bump();
  }

  DI.D = D;
  DI.CL = CL;
  DI.byKey = byKey;
  DI.store = { state, view, select, setPage, toggleFacet, setAds, setKeys,
               clearFilters, isFiltered, presenceOf, bandOf, bump };
})(window.DI);
