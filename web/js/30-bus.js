/* ── Bus: three channels, and nothing else ────────────────────────────────────
   The cost contract per channel matters more than the code:

     hover   NEVER calls setOption. ECharts gets dispatchAction({type:'highlight'})
             and DOM panels get one class flip. Coalesced to one per frame.
     select  changes the subject clinic; only subject-dependent panels update.
     filter  one memoised recompute in the store, then update() on mounted panels.

   Getting `hover` wrong is what would make a 34-clinic dashboard feel heavy. */
(function (DI) {
  "use strict";

  const subs = new Map();

  function on(channel, fn) {
    if (!subs.has(channel)) subs.set(channel, new Set());
    subs.get(channel).add(fn);
    return () => subs.get(channel).delete(fn);
  }

  function emit(channel, payload) {
    const set = subs.get(channel);
    if (!set) return;
    for (const fn of set) {
      try {
        fn(payload);
      } catch (err) {
        // One bad panel must not take the whole canvas down with it.
        console.error(`[bus:${channel}]`, err);
      }
    }
  }

  // Hover is the hot path: pointermove fires continuously, so collapse to one
  // dispatch per animation frame and drop redundant repeats of the same key.
  let lastHover = null;
  const emitHover = DI.coalesce((key, src) => {
    if (key === lastHover) return;
    lastHover = key;
    document.body.classList.toggle("hovering", !!key);
    emit("hover", { key: key || null, src: src || null });
  });

  DI.bus = { on, emit, hover: (key, src) => emitHover(key || null, src) };
})(window.DI);
