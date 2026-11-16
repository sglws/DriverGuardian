(() => {
  "use strict";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Put `ind` under the selected item of `box`: same size, same place. */
  function follow(box, ind, selected) {
    const place = () => {
      const b = selected();
      if (!b || !b.offsetWidth) { ind.style.opacity = "0"; return; }
      ind.style.opacity = "";
      ind.style.width = b.offsetWidth + "px";
      ind.style.height = b.offsetHeight + "px";
      ind.style.transform = `translate(${b.offsetLeft}px, ${b.offsetTop}px)`;
    };
    ind.style.transition = "none";            // first placement: appear in place, no slide
    place();
    setTimeout(() => { if (!reduce) ind.style.transition = ""; }, 50);
    return place;
  }

  /* ---- sidebar tabs ---- */
  const tabs = document.querySelector(".tabs");
  if (tabs) {
    const ind = Object.assign(document.createElement("span"), { className: "tab-ind" });
    ind.setAttribute("aria-hidden", "true");
    tabs.prepend(ind);
    tabs.classList.add("has-ind");
    const place = follow(tabs, ind, () => tabs.querySelector('[aria-selected="true"]'));
    new MutationObserver(place).observe(tabs, { subtree: true, attributes: true, attributeFilter: ["aria-selected"] });
    addEventListener("resize", place);
  }

  const segs = new Map();                       // .seg -> place()
  function setupSeg(seg) {
    if (segs.has(seg)) return segs.get(seg)();
    const items = () => [...seg.children].filter((c) => !c.classList.contains("seg-thumb"));
    const selected = () => items().find((c) => c.getAttribute("aria-pressed") === "true" || c.querySelector?.("input:checked"));
    if (!items().length) return;
    const thumb = Object.assign(document.createElement("span"), { className: "seg-thumb" });
    thumb.setAttribute("aria-hidden", "true");
    seg.prepend(thumb);
    seg.classList.add("has-thumb");
    const place = follow(seg, thumb, selected);
    segs.set(seg, place);
    seg.addEventListener("change", place);      // radio-button segments (the test dialog)
  }
  const scanSegs = () => document.querySelectorAll(".seg").forEach(setupSeg);
  scanSegs();
  new MutationObserver((muts) => {
    let again = false;
    for (const m of muts) {
      if (m.type === "attributes") {
        const seg = m.target.closest(".seg");
        if (seg && segs.has(seg)) segs.get(seg)(); else if (m.attributeName === "hidden" || m.attributeName === "open") again = true;
      } else if ([...m.addedNodes].some((n) => n.nodeType === 1 && !n.classList.contains("seg-thumb"))) again = true;
    }
    if (again) scanSegs();
  }).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["aria-pressed", "hidden", "open"] });
  addEventListener("resize", () => segs.forEach((place) => place()));

  if (reduce || !("IntersectionObserver" in window)) return;

  const SEL = ".live-grid > *, .trends .toolbar, .charts > .card, .drawer, .page-title, .hist-list-card, .hist-item, " +
              ".hist-detail > :not(.detail-charts), .detail-charts > .card, .tile, .doc, .doc-sec, .doc-bar";
  const STEP = 55, MAX_STEPS = 12, DURATION = 900;
  const seen = new WeakSet();
  const waiting = new Set();                   // hidden panels, revealed when they come on screen
  let graceUntil = 0;

  const onScreen = (el) => { const r = el.getBoundingClientRect(); return r.height > 0 && r.bottom > 0 && r.top < innerHeight; };
  function finish(el) {
    el.classList.remove("mat", "in");          // back to a plain element: no lingering filter or delay
    el.style.transitionDelay = "";
  }
  function hide(el) {
    el.classList.add("mat");
    waiting.add(el);
    io.observe(el);
  }
  function play(els) {
    els = els.filter((el) => el.isConnected && !el.classList.contains("in"))
             .sort((a, b) => { const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
                               return (ra.top - rb.top) || (ra.left - rb.left); });
    if (!els.length) return;
    els.forEach((el) => { waiting.delete(el); io.unobserve(el); el.classList.add("mat"); });
    void document.body.offsetWidth;            // apply the hidden state now, so the reveal below animates
    els.forEach((el, i) => {                   // no requestAnimationFrame: browsers throttle it (low power, background)
      const delay = Math.min(i, MAX_STEPS) * STEP;
      el.style.transitionDelay = delay + "ms";
      el.classList.add("in");
      setTimeout(() => { if (el.classList.contains("in")) finish(el); }, delay + DURATION + 200);
    });
  }
  document.addEventListener("transitionend", (e) => {
    if (e.propertyName === "opacity" && e.target.classList.contains("in")) finish(e.target);
  });

  const io = new IntersectionObserver((entries) => {
    play(entries.filter((en) => en.isIntersecting).map((en) => en.target));
  });
  /* the safety net: reveal anything still waiting that is on screen */
  let checkQueued = false;
  function check() {
    checkQueued = false;
    const due = [];
    for (const el of waiting) {
      if (!el.isConnected) waiting.delete(el);
      else if (onScreen(el)) due.push(el);
    }
    play(due);
  }
  const queueCheck = () => { if (!checkQueued) { checkQueued = true; setTimeout(check, 16); } };
  addEventListener("scroll", queueCheck, { passive: true });
  addEventListener("scrollend", queueCheck);
  addEventListener("resize", queueCheck);
  setInterval(() => { if (waiting.size) check(); }, 1000);

  function scan(root, force = false) {
    if (!(root instanceof Element) || root.closest(".kiosk, dialog")) return;
    const els = root.matches(SEL) ? [root] : [];
    els.push(...root.querySelectorAll(SEL));
    const batch = [];
    for (const el of els) {
      if (!el.getBoundingClientRect().height) continue;   // in a hidden view: handled when it is shown
      const fresh = !seen.has(el);
      seen.add(el);
      if (onScreen(el)) { if (force || (fresh && performance.now() < graceUntil)) batch.push(el); }
      else if (fresh || force) hide(el);
    }
    play(batch);
  }
  function pageShown() {
    graceUntil = performance.now() + 900;
    setTimeout(() => document.querySelectorAll("#app > section:not([hidden])").forEach((v) => scan(v, true)), 0);
  }

  const app = document.getElementById("app");
  pageShown();
  new MutationObserver((muts) => {
    let shown = false;
    for (const m of muts) {
      if (m.type === "attributes") { if (!m.target.hidden && m.target.parentElement === app) shown = true; }
      else m.addedNodes.forEach((n) => scan(n));
    }
    if (shown) pageShown();
  }).observe(app, { subtree: true, childList: true, attributes: true, attributeFilter: ["hidden"] });
})();
