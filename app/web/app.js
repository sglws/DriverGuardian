/* DriverGuardian dashboard - no external libraries (the Pi may be offline). */
"use strict";

const $ = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";

/* ================================================================ basics */
const ICON_PATHS = {
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.8 2.8L16 10"/>',
  alert: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
  stop: '<path d="M8 3h8l5 5v8l-5 5H8l-5-5V8z"/><path d="m9 9 6 6M15 9l-6 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  pause: '<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18M10.6 6a9.7 9.7 0 0 1 10.9 6 13 13 0 0 1-2.5 3.3M6.5 7.6A13 13 0 0 0 2.5 12S6 18.5 12 18.5a9.5 9.5 0 0 0 4.2-1"/>',
  blink: '<path d="M3 10c2.5 3 5.5 4.5 9 4.5s6.5-1.5 9-4.5M6 13.5 4.5 16M12 15v3M18 13.5l1.5 2.5"/>',
  mouth: '<circle cx="12" cy="12" r="9"/><path d="M8 14.5c1 1.3 2.4 2 4 2s3-.7 4-2M9 9.5v.01M15 9.5v.01"/>',
  head: '<circle cx="12" cy="8" r="4"/><path d="M5 21a7 7 0 0 1 14 0"/>',
  phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
  cup: '<path d="M5 8h11v6a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5zM16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 3.5v2M11 3v2.5M14 3.5v2"/>',
  smoke: '<path d="M3 15h14v4H3zM20 15v4M17 11c0-1.5 1-2 1-3.5S17 5 17 4M20 11c0-1.5 1-2 1-3.5S20 5 20 4"/>',
  belt: '<path d="M5 3l14 18M9 3v5M15 16v5"/><rect x="10" y="9" width="5" height="4" rx="1" transform="rotate(38 12.5 11)"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  temp: '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/>',
  memory: '<rect x="3" y="7" width="18" height="10" rx="1.5"/><path d="M7 7v10M11 7v10M15 7v10M19 7v10"/>',
  box: '<path d="M4 7.5 12 3l8 4.5v9L12 21l-8-4.5z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
  bt: '<path d="m7 7 10 10-5 4V3l5 4L7 17"/>',
  voice: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/>',
  mute: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="m16 9 5 5M21 9l-5 5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  gauge: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m12 18 4-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>',
  play: '<path d="M7 5v14l11-7z"/>',
  pauseBars: '<path d="M9 5v14M15 5v14"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6"/>',
  bottle: '<path d="M10 2.5h4M10.5 2.5v4.2L8.3 9.6a3 3 0 0 0-.6 1.8V20a1.5 1.5 0 0 0 1.5 1.5h5.6a1.5 1.5 0 0 0 1.5-1.5v-8.6a3 3 0 0 0-.6-1.8l-2.2-2.9V2.5"/><path d="M7.7 13h8.6"/>',
  turn: '<circle cx="10" cy="8" r="3.5"/><path d="M3.5 20a6.5 6.5 0 0 1 9.5-5.8"/><path d="m17 12 3.5 3.5L17 19M20.5 15.5H14"/>',
  flask: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/><path d="M7.5 15h9"/>',
  car: '<path d="M5 17h14v-4l-2-5H7l-2 5zM5 13h14"/><circle cx="8" cy="17" r="1.8"/><circle cx="16" cy="17" r="1.8"/>',
  ruler: '<path d="M3 17 17 3l4 4L7 21z"/><path d="m7 13 2 2M10 10l2 2M13 7l2 2"/>',
  edge: '<path d="M3 8h12l6 8H3z"/><path d="M15 8v8"/>',
  print: '<path d="M7 9V3h10v6M7 17H4v-7h16v7h-3"/><rect x="7" y="14" width="10" height="7"/>',
  compare: '<path d="M8 3v18M16 3v18M4 7h4M4 12h4M16 9h4M16 15h4"/>',
  report: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>',
  back: '<path d="M15 6l-6 6 6 6"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  unlock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/>',
};
function icon(name, cls = "i") {
  const s = document.createElementNS(SVGNS, "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("class", cls);
  s.setAttribute("aria-hidden", "true");
  s.innerHTML = ICON_PATHS[name] || "";   // static, trusted strings only
  return s;
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function svgEl(tag, attrs) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}

const LEVELS = {
  SAFE:    { word: "Safe",    token: "--good",     icon: "check", tone: "good" },
  LOW:     { word: "Low",     token: "--warning",  icon: "info",  tone: "warning" },
  MEDIUM:  { word: "Medium",  token: "--serious",  icon: "alert", tone: "serious" },
  HIGH:    { word: "High",    token: "--critical", icon: "stop",  tone: "critical" },
  WAITING: { word: "Waiting", token: "--neutral",  icon: "clock", tone: "info" },
};
const RISK_ORDER = ["WAITING", "SAFE", "LOW", "MEDIUM", "HIGH"];
const lv = (r) => LEVELS[r] || LEVELS.WAITING;
const CASES = {
  NONE: "All clear", MICROSLEEP: "Eyes closing", SLEEP: "Driver asleep", YAWN: "Yawning",
  LEAN: "Head leaning", LEAN_PROLONGED: "Prolonged head lean", TURN: "Looking away",
  TURN_PROLONGED: "Prolonged look-away", SEATBELT: "Seatbelt off", PHONE: "Phone use",
  PHONE_REPEAT: "Repeated phone use", CONSUMPTION: "Eating, drinking or smoking",
  CONSUMPTION_REPEAT: "Repeated eating, drinking or smoking", BLOCKED: "Camera blocked",
  ABSENT: "Driver not in seat", PRE_DRIVE: "Waiting for seatbelt", CALIBRATING: "Calibrating",
  PAUSED: "Monitoring paused", TEST: "Test running",
};
const caseName = (c) => CASES[c] || (c ? c.replace(/_/g, " ").toLowerCase() : "—");
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s);
const fmt = (v, d = 2) => (v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
const signed = (v, d = 1) => (v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d));
const pad2 = (n) => String(n).padStart(2, "0");
function clock(ts, withSec = true) {
  const d = new Date(ts * 1000);
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}${withSec ? ":" + pad2(d.getSeconds()) : ""}`;
}
function dateLabel(ts) {
  const d = new Date(ts * 1000), today = new Date();
  const same = d.toDateString() === today.toDateString();
  const yest = new Date(today.getTime() - 864e5).toDateString() === d.toDateString();
  const day = same ? "Today" : yest ? "Yesterday" : d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  return `${day}, ${clock(ts, false)}`;
}
function duration(sec) {
  if (sec == null || Number.isNaN(sec)) return "—";
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  if (h) return `${h}h ${pad2(m)}m`;
  if (m) return `${m}m ${pad2(s)}s`;
  return `${s}s`;
}

/* ================================================================ theme */
const THEMES = ["auto", "light", "dark"];
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } },
};
let theme = store.get("dg-theme", "dark");   // the cockpit is designed night-first
function setTip(node, text) { node.dataset.tip = text; node.setAttribute("aria-label", text); }
function applyTheme() {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  setTip($("btn-theme"), `Theme: ${theme === "auto" ? "follows the system" : theme} — click to change`);
}
$("btn-theme").onclick = () => { theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]; store.set("dg-theme", theme); applyTheme(); };
applyTheme();

/* ================================================================ api, toasts, dialogs */
async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}
/* Changes need the dashboard PIN (watching doesn't). Each browser asks once
   and remembers it; a wrong PIN asks again, too many lock it out for a minute. */
let pin = store.get("dg-pin", "");
async function rawApi(method, url, body, usePin = pin) {
  const r = await fetch(url, { method, headers: { "X-DriverGuardian": "1", "X-DG-PIN": usePin, "Content-Type": "application/json" },
                               body: body ? JSON.stringify(body) : undefined });
  let data = {};
  try { data = await r.json(); } catch (e) { /* empty */ }
  return { r, data };
}
async function askPin(again) {
  const v = await dialog({ title: again ? "Wrong PIN" : "Enter the dashboard PIN",
    body: again ? "That PIN wasn't accepted — try again." : "Controls are protected so only the test team can change things. Watching needs no PIN.\nThis browser will remember it.",
    confirm: "Unlock", input: { label: "PIN", type: "password", placeholder: "PIN", value: "" } });
  if (!v) return false;
  pin = v; store.set("dg-pin", v); renderLock();
  return true;
}
async function api(method, url, body) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const { r, data } = await rawApi(method, url, body);
    if (r.status === 401 && data.pin) {
      if (pin && attempt === 0) { pin = ""; store.set("dg-pin", ""); }   // a saved PIN that has since changed
      if (!(await askPin(attempt > 0))) throw new Error("PIN required");
      continue;
    }
    if (!r.ok) throw new Error(data.error || `request failed (${r.status})`);
    return data;
  }
  throw new Error("PIN required");
}
function renderLock() {
  const b = $("btn-lock");
  b.hidden = !(state && state.pin_required);
  b.replaceChildren(icon(pin ? "unlock" : "lock"));
  setTip(b, pin ? "Unlocked on this device — click to lock" : "Controls locked — click to enter the PIN");
}
$("btn-lock").onclick = async () => {
  if (pin) { pin = ""; store.set("dg-pin", ""); renderLock(); toast("Controls locked on this device"); return; }
  if (!(await askPin(false))) return;
  const { r, data } = await rawApi("POST", "/api/auth", { pin });
  if (r.ok) toast("Controls unlocked");
  else { pin = ""; store.set("dg-pin", ""); renderLock(); toast(data.error || "Wrong PIN", true); }
};
function toast(msg, err = false) {
  const t = el("div", `toast${err ? " err" : ""}`);
  t.append(icon(err ? "alert" : "check"), document.createTextNode(msg));
  $("toasts").append(t);
  setTimeout(() => { t.classList.add("out"); t.addEventListener("animationend", () => t.remove()); setTimeout(() => t.remove(), 400); }, 3000);
}
const dlg = $("dlg");
function dialog({ title, body = "", confirm = "OK", danger = false, input = null, select = null }) {
  $("dlg-title").textContent = title;
  $("dlg-body").textContent = body;
  $("dlg-body").hidden = !body;
  $("dlg-field").hidden = !input;
  $("dlg-sfield").hidden = !select;
  if (input) {
    $("dlg-label").textContent = input.label || ""; $("dlg-input").value = input.value || ""; $("dlg-input").placeholder = input.placeholder || "";
    $("dlg-input").type = input.type || "text";
    $("dlg-input").autocomplete = input.type === "password" ? "current-password" : "off";
  }
  if (select) {
    $("dlg-slabel").textContent = select.label || "";
    $("dlg-select").replaceChildren(...select.options.map(([v, label]) => { const o = el("option", null, label); o.value = String(v); return o; }));
    if (select.value != null) $("dlg-select").value = String(select.value);
  }
  const ok = $("dlg-ok");
  ok.textContent = confirm;
  ok.className = danger ? "danger solid" : "primary";
  return new Promise((resolve) => {
    dlg.onclose = () => {
      const val = dlg.returnValue === "ok" ? (input ? $("dlg-input").value.trim() : select ? $("dlg-select").value : true) : null;
      if (input && input.type === "password") $("dlg-input").value = "";
      resolve(val);
    };
    dlg.returnValue = "";
    dlg.showModal();
    (input ? $("dlg-input") : select ? $("dlg-select") : $("dlg-cancel")).focus();
  });
}

/* ================================================================ tabs */
/* Views: #live, #history, #report/ID, #compare/A/B and #kiosk (presentation). */
let view = "live";
function setView(v, args = []) {
  view = v;
  $("tab-live").setAttribute("aria-selected", String(v === "live"));
  $("tab-history").setAttribute("aria-selected", String(v !== "live"));
  $("view-live").hidden = v !== "live";
  $("view-history").hidden = v !== "history";
  $("view-report").hidden = v !== "report";
  $("view-compare").hidden = v !== "compare";
  document.body.dataset.view = v;
  if (v !== "report") document.title = "DriverGuardian Monitor";
  if (v === "live") { startVideo(); liveCharts.forEach((c) => c.render()); } else stopVideo();
  if (v === "history") loadHistory();
  if (v === "report") renderReport(args[0]);
  if (v === "compare") renderCompare(args[0], args[1]);
  const hash = ["report", "compare"].includes(v) ? `#${[v, ...args].join("/")}` : kioskOn ? "#kiosk" : `#${v}`;
  if (location.hash !== hash) history.replaceState(null, "", hash);
}
function route() {
  const [v, a, b] = location.hash.slice(1).split("/");
  if (v === "kiosk") { setView("live"); setKiosk(true); return; }
  if (kioskOn) setKiosk(false);
  if (v === "report" && Number(a)) setView("report", [Number(a)]);
  else if (v === "compare" && Number(a) && Number(b)) setView("compare", [Number(a), Number(b)]);
  else setView(v === "history" ? "history" : "live");
}
window.addEventListener("hashchange", route);
/* View changes cross-fade where the browser supports view transitions. */
function goView(v) {
  if (view === v) return;
  if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) document.startViewTransition(() => setView(v));
  else setView(v);
}
$("tab-live").onclick = () => { if (kioskOn) setKiosk(false); goView("live"); };
$("tab-history").onclick = () => goView("history");

/* ================================================================ video */
const video = $("video");
let videoOn = false;
function startVideo() { if (videoOn) return; videoOn = true; video.src = "/stream.mjpg?t=" + Date.now(); }
function stopVideo() { videoOn = false; video.removeAttribute("src"); video.classList.remove("ready"); }
video.onerror = () => { if (!videoOn) return; video.classList.remove("ready"); $("video-wait").hidden = false; videoOn = false; setTimeout(() => view === "live" && startVideo(), 2000); };
video.onload = () => { $("video-wait").hidden = true; video.classList.add("ready"); };
$("btn-full").onclick = () => {
  const box = kioskOn ? $("kiosk") : $("video-box");
  if (document.fullscreenElement) document.exitFullscreen();
  else if (box.requestFullscreen) box.requestFullscreen();
};

/* Presentation mode: the video and a giant risk level, full screen. */
let kioskOn = false;
function setKiosk(on) {
  if (on === kioskOn) return;
  kioskOn = on;
  const box = $("video-box");
  $("kiosk").hidden = !on;
  document.body.classList.toggle("kiosk-on", on);
  if (on) {
    $("k-video").append(box);
    const k = $("kiosk");
    if (k.requestFullscreen && !document.fullscreenElement) k.requestFullscreen().catch(() => { /* needs a click; still works windowed */ });
    if (state) renderKiosk();
  } else {
    document.querySelector("#view-live .live-grid").prepend(box);
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }
  if (videoOn) { stopVideo(); startVideo(); }   // moving the box can drop the stream
  const hash = on ? "#kiosk" : "#live";
  if (location.hash !== hash) history.replaceState(null, "", hash);
}
$("btn-kiosk").onclick = () => { if (view !== "live") setView("live"); setKiosk(!kioskOn); };
$("k-exit").onclick = () => setKiosk(false);
function renderKiosk() {
  const L = lv(state.risk), k = $("kiosk");
  const word = state.calibrating ? "Calibrating" : state.paused ? "Paused" : (state.test && state.test.active) ? "Testing" : L.word;
  k.style.setProperty("--level", `var(${state.paused || state.calibrating ? "--neutral" : L.token})`);
  setAnimated($("k-level"), word);
  // as large as the panel allows for this word
  const kl = $("k-level"), room = kl.parentElement.clientWidth - parseFloat(getComputedStyle(kl.parentElement).paddingLeft) * 2;
  kl.style.fontSize = `${Math.max(40, Math.min(150, room / (0.6 * word.length)))}px`;
  const cn = caseName(state.case);
  $("k-case").textContent = cn === word || state.case === "NONE" ? "" : cn;
  const msg = (state.messages || [])[0] || "";
  $("k-msg").textContent = msg === cn ? "" : msg;
  const active = !state.paused && !state.calibrating;
  k.classList.toggle("attn", active && state.risk === "HIGH");
  const idx = active && state.case !== "TEST" ? ["SAFE", "LOW", "MEDIUM", "HIGH"].indexOf(state.risk) : -1;
  kioskGauge = kioskGauge || buildGauge($("k-gauge"));
  kioskGauge.set(idx);
  const f = $("k-facts"); f.replaceChildren();
  const fact = (label, value) => { const d = el("div"); d.append(el("span", null, label), el("b", null, value)); f.append(d); };
  fact("For", duration((Date.now() - riskSince.at) / 1000));
  const veh = state.links && state.links.vehicle;
  if (veh) fact("Vehicle speed", veh.estop ? "Stopped" : `${veh.speed_pct ?? "—"} %`);
  const sess = state.session || {};
  const alerts = Object.values(sess.alerts || {}).reduce((a, b) => a + b, 0);
  fact("Alerts this session", String(alerts));
  fact("Session", duration(sess.uptime_s));
}

/* ================================================================ browser sound */
let soundOn = store.get("dg-sound", "0") === "1";
let audioCtx = null;
function setSound(on) {
  soundOn = on; store.set("dg-sound", on ? "1" : "0");
  $("btn-sound").setAttribute("aria-pressed", String(on));
  setTip($("btn-sound"), on ? "Browser sound on (high and medium risk)" : "Browser sound off — click to hear high risk here");
}
function beep(times, freq) {
  if (!soundOn) return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    for (let i = 0; i < times; i++) {
      const o = audioCtx.createOscillator(), g = audioCtx.createGain(), t = audioCtx.currentTime + i * 0.22;
      o.frequency.value = freq; o.type = "sine";
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.25, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
      o.connect(g).connect(audioCtx.destination); o.start(t); o.stop(t + 0.18);
    }
  } catch (e) { /* audio unavailable */ }
}
$("btn-sound").onclick = () => { setSound(!soundOn); if (soundOn) { beep(1, 880); toast("Browser sound on"); } };
setSound(soundOn);

/* ================================================================ live state */
let state = null, lastOk = 0, stopped = false;
let riskSince = { key: null, at: Date.now() };

function setConnection() {
  const fresh = Date.now() - lastOk < 3000 && state && state.age_sec != null && state.age_sec < 3;
  const c = $("conn");
  c.classList.toggle("live", !!fresh);
  c.classList.toggle("stale", !fresh && lastOk > 0);
  $("conn-text").textContent = fresh ? "Live" : stopped ? "Stopped" : lastOk ? "Reconnecting…" : "Connecting…";
  $("app").classList.toggle("stale-data", !fresh && lastOk > 0);
  const banner = $("banner");
  if (stopped) { banner.hidden = false; banner.textContent = "DriverGuardian was stopped. Start it again on the Pi to continue."; }
  else if (!fresh && lastOk > 0 && Date.now() - lastOk > 5000) { banner.hidden = false; banner.textContent = "Connection to the app lost — reconnecting…"; }
  else banner.hidden = true;
}

async function pollState() {
  try {
    state = await getJSON("/api/state");
    lastOk = Date.now();
    if (stopped) { stopped = false; toast("DriverGuardian is running again"); }
    renderLive();
  } catch (e) { /* keep the last render, marked stale */ }
  setConnection();
}

function renderLive() {
  if (!state || !state.risk) return;
  $("app").classList.remove("loading");
  if (video.naturalWidth > 0) { $("video-wait").hidden = true; video.classList.add("ready"); }
  const box = $("video-box");
  box.dataset.level = state.paused || state.calibrating ? "" : state.risk;
  box.classList.toggle("calibrating", !!state.calibrating);
  renderSessionBar();
  renderHero();
  renderChips();
  renderVehicle();
  renderTest();
  renderDiagSummary();
  if ($("diag").open) renderPanels();
  renderLock();
  if (kioskOn) renderKiosk();
  const fps = state.perf && state.perf.fps;
  $("video-fps").textContent = fps ? `${fmt(fps, 1)} FPS` : "";
  $("video-fps").hidden = !fps;
  $("calib").hidden = !state.calibrating;
  $("calib-bar").style.width = `${Math.round((state.calib_progress || 0) * 100)}%`;
  $("paused-cover").hidden = !state.paused;
  const pill = $("live-pill");
  pill.classList.toggle("paused", !!state.paused);
  $("live-pill-text").textContent = state.paused ? "PAUSED" : "LIVE";
}

/* ---------------- session bar */
let nameEditing = false;
function renderSessionBar() {
  const s = state.session || {};
  const badge = $("state-badge");
  const mode = state.calibrating ? "calibrating" : state.paused ? "paused" : "monitoring";
  badge.className = `state-badge ${mode}`;
  $("state-text").textContent = { calibrating: "Calibrating", paused: "Paused", monitoring: "Monitoring" }[mode];
  const input = $("session-name");
  if (!nameEditing && document.activeElement !== input) input.value = s.label || "";
  $("session-meta").textContent = s.started_ts
    ? `${s.recording ? "Recording" : "Not recorded"} since ${clock(s.started_ts, false)}, running ${duration(s.uptime_s)}`
    : "";
  const testing = !!(state.test && state.test.active), tb = $("btn-test");
  if (tb.dataset.on !== String(testing)) {
    tb.dataset.on = String(testing);
    tb.replaceChildren(icon(testing ? "stop" : "flask"), el("span", null, testing ? "Stop test" : "Test"));
    tb.classList.toggle("danger", testing);
  }
  const pause = $("btn-pause");
  pause.setAttribute("aria-pressed", String(!!state.paused));
  pause.replaceChildren(icon(state.paused ? "play" : "pauseBars"), el("span", null, state.paused ? "Resume" : "Pause"));
  const muted = !!(state.links && state.links.muted);
  const mute = $("btn-mute");
  mute.setAttribute("aria-pressed", String(muted));
  if (mute.dataset.muted !== String(muted)) {
    mute.dataset.muted = String(muted);
    mute.replaceChildren(icon(muted ? "mute" : "voice"));
    setTip(mute, muted ? "Voice alerts muted — click to unmute" : "Mute the spoken alerts");
  }
}
const nameInput = $("session-name");
nameInput.addEventListener("focus", () => { nameEditing = true; });
nameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") nameInput.blur(); if (e.key === "Escape") { nameInput.value = (state.session || {}).label || ""; nameInput.blur(); } });
nameInput.addEventListener("blur", async () => {
  nameEditing = false;
  const s = state && state.session, v = nameInput.value.trim();
  if (!s || !s.id || !v || v === s.label) { if (s) nameInput.value = s.label || ""; return; }
  try { await api("POST", `/api/sessions/${s.id}`, { label: v }); s.label = v; toast("Session renamed"); }
  catch (e) { toast(`Rename failed: ${e.message}`, true); }
});

async function control(action, extra = {}, okMsg = "") {
  try { await api("POST", "/api/control", { action, ...extra }); if (okMsg) toast(okMsg); pollState(); return true; }
  catch (e) { toast(`${cap(action.replace("_", " "))} failed: ${e.message}`, true); return false; }
}
async function togglePause() { if (state) await control(state.paused ? "resume" : "pause", {}, state.paused ? "Monitoring resumed" : "Monitoring paused"); }
async function addMarker() {
  const text = await dialog({ title: "Add a marker", body: "Marks this moment in the session — it appears in the event log, on the risk timeline and in the saved session.",
                              confirm: "Add marker", input: { label: "Note", placeholder: "e.g. phone test starts", value: "" } });
  if (text === null) return;
  try { await api("POST", "/api/marker", { text: text || "Marker" }); toast("Marker added"); pollEvents(); }
  catch (e) { toast(`Marker failed: ${e.message}`, true); }
}
$("btn-pause").onclick = togglePause;
$("btn-mark").onclick = addMarker;
$("btn-recal").onclick = async () => {
  if (await dialog({ title: "Recalibrate now?", body: "The driver should sit normally and look straight at the camera, eyes open and mouth closed, for 3 seconds.", confirm: "Recalibrate" }))
    control("recalibrate", {}, "Recalibrating — look straight at the camera");
};
$("btn-mute").onclick = () => { const muted = !!(state && state.links && state.links.muted); control(muted ? "unmute" : "mute", {}, muted ? "Voice alerts on" : "Voice alerts muted"); };
$("btn-snap").onclick = () => {
  const d = new Date();
  $("btn-snap").download = `driverguardian-${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}-${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}.jpg`;
};
$("btn-new").onclick = async () => {
  const label = await dialog({ title: "Start a new session?", body: "The current session is saved to History. The new session starts with a 3-second calibration.",
                               confirm: "Start new session", input: { label: "Name for the new session (optional)", placeholder: "e.g. Test 4 — dim light — Sara" } });
  if (label === null) return;
  if (await control("new_session", { label }, "New session started")) { liveSamples = []; lastT = -1; liveEvents = []; renderEventList($("events"), [], liveFilter, $("ev-count")); }
};
$("btn-stop").onclick = async () => {
  const ok = await dialog({ title: "Stop DriverGuardian?", danger: true, confirm: "Stop the app",
    body: "Monitoring stops and the session is saved to History.\nTo start again, run the app on the Pi (or restart its service)." });
  if (!ok) return;
  if (await control("stop", {}, "Stopping — the session is being saved")) { stopped = true; setConnection(); }
};

/* ---------------- "More" menu */
const moreBtn = $("btn-more"), moreMenu = $("more-menu");
function setMenu(open) {
  moreMenu.hidden = !open;
  moreBtn.setAttribute("aria-expanded", String(open));
  if (open) moreMenu.querySelector(".mi").focus();
}
moreBtn.onclick = (e) => { e.stopPropagation(); setMenu(moreMenu.hidden); };
document.addEventListener("click", (e) => { if (!moreMenu.hidden && !e.target.closest(".menu-wrap")) setMenu(false); });
moreMenu.addEventListener("click", (e) => { if (e.target.closest(".mi")) setMenu(false); });
moreMenu.addEventListener("keydown", (e) => {
  const items = [...moreMenu.querySelectorAll(".mi")], i = items.indexOf(document.activeElement);
  if (e.key === "ArrowDown") { items[(i + 1) % items.length].focus(); e.preventDefault(); }
  else if (e.key === "ArrowUp") { items[(i - 1 + items.length) % items.length].focus(); e.preventDefault(); }
  else if (e.key === "Escape" || e.key === "Tab") { setMenu(false); if (e.key === "Escape") moreBtn.focus(); }
});
$("mi-kiosk").onclick = () => setKiosk(true);
const showHelp = () => { const d = $("help-dlg"); if (!d.open) d.showModal(); };
$("mi-help").onclick = showHelp;
$("btn-help").onclick = showHelp;

/* ---------------- hero */
function setAnimated(node, text) {
  if (node.textContent === text) return;
  node.textContent = text;
  node.classList.remove("changed");
  void node.offsetWidth;           // restart the animation
  node.classList.add("changed");
}
/* The risk gauge: a 220° dial from Safe to High with a needle, like the
   speedometer it sits beside in a car. */
const GAUGE = { cx: 120, cy: 124, r: 96, start: -110, sweep: 220 };
function gaugePoint(a, r) { const t = (a * Math.PI) / 180; return [GAUGE.cx + r * Math.sin(t), GAUGE.cy - r * Math.cos(t)]; }
function arcPath(a0, a1, r) {
  const [x0, y0] = gaugePoint(a0, r), [x1, y1] = gaugePoint(a1, r);
  return `M${x0.toFixed(2)},${y0.toFixed(2)} A${r},${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1.toFixed(2)},${y1.toFixed(2)}`;
}
function buildGauge(host) {
  const levels = ["SAFE", "LOW", "MEDIUM", "HIGH"], seg = GAUGE.sweep / levels.length;
  const svg = svgEl("svg", { viewBox: "-26 -6 292 166", class: "gauge-svg" });
  for (let i = 0; i <= 24; i++) {
    const a = GAUGE.start + (GAUGE.sweep * i) / 24, major = i % 6 === 0;
    const [x0, y0] = gaugePoint(a, 80), [x1, y1] = gaugePoint(a, major ? 71 : 75);
    svg.append(svgEl("line", { x1: x0, y1: y0, x2: x1, y2: y1, class: major ? "g-tick major" : "g-tick" }));
  }
  const segs = levels.map((r, i) => {
    const a0 = GAUGE.start + i * seg, path = svgEl("path", { d: arcPath(a0 + 1.6, a0 + seg - 1.6, GAUGE.r), class: "g-seg" });
    path.style.setProperty("--c", `var(${lv(r).token})`);
    const mid = a0 + seg / 2, side = mid < -40 ? "end" : mid > 40 ? "start" : "middle";   // side labels sit outside the arc
    const [lx, ly] = gaugePoint(mid, GAUGE.r + (side === "middle" ? 15 : 12));
    const t = svgEl("text", { x: lx, y: ly + 4, class: "g-label", "text-anchor": side }); t.textContent = lv(r).word;
    svg.append(path, t);
    return { path, t };
  });
  const needle = svgEl("g", { class: "g-needle" });
  needle.append(svgEl("path", { d: `M${GAUGE.cx - 3.2},${GAUGE.cy} L${GAUGE.cx},${GAUGE.cy - GAUGE.r + 8} L${GAUGE.cx + 3.2},${GAUGE.cy} Z`, class: "g-needle-body" }),
    svgEl("circle", { cx: GAUGE.cx, cy: GAUGE.cy, r: 7.5, class: "g-hub" }));
  svg.append(needle);
  host.replaceChildren(svg);
  let last = null;
  return {
    set(idx) {
      if (idx === last) return;
      last = idx;
      segs.forEach((g, i) => { g.path.classList.toggle("on", i === idx); g.path.classList.toggle("past", idx > 0 && i < idx); g.t.classList.toggle("on", i === idx); });
      const a = idx < 0 ? GAUGE.start : GAUGE.start + idx * seg + seg / 2;   // at rest: on zero, like a parked car
      needle.style.transform = `rotate(${a}deg)`;
      host.dataset.idx = String(idx);
    },
  };
}
let heroGauge = null, kioskGauge = null;
function renderHero() {
  const L = lv(state.risk);
  const key = `${state.risk}|${state.paused}|${state.calibrating}`;
  if (riskSince.key !== key) riskSince = { key, at: Date.now() };
  const hero = $("hero");
  const lvToken = state.paused || state.calibrating || state.case === "TEST" ? "--neutral" : L.token;
  hero.style.setProperty("--level", `var(${lvToken})`);
  document.documentElement.style.setProperty("--amb", `var(${lvToken})`);   // the cockpit's ambient light
  const levelWord = state.calibrating ? "Calibrating" : state.paused ? "Paused" : state.case === "TEST" ? "Testing" : L.word;
  setAnimated($("hero-level"), levelWord);
  setAnimated($("hero-case"), caseName(state.case) === levelWord ? "" : caseName(state.case));
  const active = !state.paused && !state.calibrating;
  hero.classList.toggle("attn", active && state.risk === "HIGH");
  const idx = active && state.case !== "TEST" ? ["SAFE", "LOW", "MEDIUM", "HIGH"].indexOf(state.risk) : -1;
  heroGauge = heroGauge || buildGauge($("gauge"));
  heroGauge.set(idx);
  const msg = (state.messages || [])[0] || "";
  // the engine's message often just restates the reason ("Eating/drinking/smoking") - say it once
  const words = (t) => String(t || "").toLowerCase().split(/[^a-z]+/).filter((w) => w && !["or", "and", "the", "a"].includes(w));
  const said = new Set([...words(caseName(state.case)), ...words(state.case)]);
  $("hero-msg").textContent = !msg || words(msg).every((w) => said.has(w)) ? "" : msg;
  hero.dataset.tone = state.paused || state.calibrating || state.case === "TEST" ? "info" : L.tone;
  $("hero-for").textContent = duration((Date.now() - riskSince.at) / 1000);
  $("hero-since").textContent = clock(riskSince.at / 1000);
  $("hero-score").textContent = state.score != null ? state.score : "—";
  renderTopRisk(levelWord, L);
}

/* Live risk in the top bar - whenever the hero card is out of sight
   (scrolled away, or on the History tab). */
let heroVisible = true;
if ("IntersectionObserver" in window)
  new IntersectionObserver((ents) => { heroVisible = ents[0].isIntersecting; if (state) renderHero(); }, { rootMargin: "-64px 0px 0px 0px" }).observe($("hero"));
function renderTopRisk(word, L) {
  const b = $("top-risk"), show = !kioskOn && !!state && (view !== "live" || !heroVisible);
  b.hidden = !show;
  if (!show) return;
  b.dataset.tone = state.paused || state.calibrating || state.case === "TEST" ? "info" : L.tone;
  $("top-risk-level").textContent = word;
  const cn = caseName(state.case);
  $("top-risk-case").textContent = state.case && !["NONE", "TEST", "PAUSED", "CALIBRATING"].includes(state.case) && cn !== word ? cn : "";
}
$("top-risk").onclick = () => { if (view !== "live") setView("live"); window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); };

/* ---------------- chips */
function renderChips() {
  const s = state, o = s.objects || {}, cam = s.camera || {};
  // without a face the app's EAR/MAR/pose are placeholders, not measurements
  const e = s.face_found ? s.eyes : null, m = s.face_found ? s.mouth : null, h = s.face_found ? s.head : null;
  const noFace = s.calibrating ? "calibrating" : "no face";
  const rows = [];
  if (e) {
    const closedLong = e.closed && e.closed_sec >= 1;
    rows.push(["eyes", e.closed ? "eyeOff" : "eye", "Eyes", e.looking_down ? "Looking down" : e.closed ? `Closed ${fmt(e.closed_sec, 1)} s` : "Open",
      `EAR ${fmt(e.ear)}, closed below ${fmt(e.ear_thr)}`, closedLong ? "crit" : e.closed ? "warn" : "ok"]);
    rows.push(["blinks", "blink", "Blinks", `${e.blink_rate} in last ${Math.round(e.blink_window_sec)} s`, `${e.blinks_total} in session`, e.level === "DROWSY" ? "warn" : ""]);
  } else {
    rows.push(["eyes", "eye", "Eyes", "—", noFace, ""]);
    rows.push(["blinks", "blink", "Blinks", "—", "", ""]);
  }
  if (m) rows.push(["mouth", "mouth", "Mouth", m.yawning ? "Yawning" : m.open ? "Open" : "Closed", `MAR ${fmt(m.mar)}, ${m.yawns_total} yawn${m.yawns_total === 1 ? "" : "s"}`, m.yawning ? "warn" : "ok"]);
  else rows.push(["mouth", "mouth", "Mouth", "—", noFace, ""]);
  if (h) {
    const dir = [h.pitch_label !== "FORWARD" ? cap(h.pitch_label.replace("/", " / ")) : null, h.yaw_label !== "CENTER" ? cap(h.yaw_label) : null].filter(Boolean).join(", ") || "Forward";
    const tone = h.turn_risk === "HIGH" ? "crit" : (h.turn_risk !== "NONE" || h.lean_sec > 0) ? "warn" : "ok";
    rows.push(["head", "head", "Head", dir, `pitch ${signed(h.pitch)}°  yaw ${signed(h.yaw)}°`, tone]);
  } else rows.push(["head", "head", "Head", "—", noFace, ""]);
  const det = (v) => (v == null ? "Not supported" : v ? "Detected" : "Not detected");
  rows.push(["phone", "phone", "Phone", det(o.phone), "", o.phone ? "crit" : o.phone === false ? "ok" : ""]);
  rows.push(["consume", "cup", "Eating / drinking", det(o.consumption), "", o.consumption ? "warn" : o.consumption === false ? "ok" : ""]);
  rows.push(["smoke", "smoke", "Smoking", det(o.cigarette), "", o.cigarette ? "warn" : o.cigarette === false ? "ok" : ""]);
  const sb = o.seatbelt;
  rows.push(["belt", "belt", "Seatbelt", sb === "ON" ? "On" : sb === "OFF" ? "Off" : sb === "N/A" ? "Not supported" : "Not seen yet", "", sb === "OFF" ? "crit" : sb === "ON" ? "ok" : "warn"]);
  const pres = s.presence;
  rows.push(["driver", "user", "Driver", pres === "DRIVER_PRESENT" ? "Present" : pres === "DRIVER_ABSENT" ? "Not in seat" : pres === "CAMERA_BLOCKED" ? "Camera blocked" : "—",
    s.face_found ? "face tracked" : "no face", pres && pres !== "DRIVER_PRESENT" ? "crit" : pres ? "ok" : ""]);
  rows.push(["cam", "sun", "Lighting", cam.low_light ? "Low light" : "Normal", `brightness ${cam.brightness != null ? cam.brightness : "—"}${cam.low_light ? ", enhanced" : ""}`, cam.low_light ? "warn" : ""]);
  // cabin air sensors on the Arduino Uno (shown and recorded; they don't change the risk)
  const cab = s.cabin, unoOn = s.links && s.links.uno === "connected";
  const air = (key, label, ic) => {
    if (!cab) return [key, ic, label, unoOn ? "No reading yet" : "Not connected", unoOn ? "" : "Arduino Uno on USB", ""];
    if (!cab.warm) return [key, ic, label, "Warming up", `${duration(cab.warmup_left_s)} left, raw ${cab[key]}`, ""];
    const rel = cab[`${key}_rel`];
    return [key, ic, label, rel == null ? "Measuring clean air" : `${fmt(rel, 2)}× clean air`, `raw ${cab[key]}, ${fmt(cab[`${key}_v`], 2)} V`,
      rel != null && rel >= 1.5 ? "warn" : "ok"];
  };
  rows.push(air("mq3", "Alcohol (MQ-3)", "bottle"), air("mq2", "Smoke, gas (MQ-2)", "smoke"));
  // One line per signal; the ones that need attention are marked.
  const box = $("chips");
  box.replaceChildren(...rows.map(([, ic, label, value, extra, tone]) => {
    const row = el("div", `rd ${tone || ""}`), dt = el("dt"), dd = el("dd");
    dt.append(icon(ic), document.createTextNode(label));
    dd.append(el("b", null, value));
    if (extra) dd.append(el("small", null, extra));
    row.append(dt, dd);
    return row;
  }));
  const hot = rows.filter((r) => r[5] === "warn" || r[5] === "crit").length;
  $("chips-sub").textContent = hot ? `${hot} need${hot === 1 ? "s" : ""} attention` : "all normal";
  renderTelltales();
  renderChain();
}
/* Warning lamps under the gauge, lit the way a car's tell-tales are:
   amber for a warning, red for danger, dark when all is well. */
const TELLTALES = [
  { icon: "eyeOff", label: "Eyes closed", on: (s) => (s.face_found && s.eyes && s.eyes.closed ? (s.eyes.closed_sec >= 1 ? "red" : "amber") : null) },
  { icon: "mouth", label: "Yawning", on: (s) => (s.face_found && s.mouth && s.mouth.yawning ? "amber" : null) },
  { icon: "head", label: "Head lean", on: (s) => (s.face_found && s.head && s.head.lean_sec > 0 ? "amber" : null) },
  { icon: "turn", label: "Looking away", on: (s) => (s.face_found && s.head && s.head.turn_risk && s.head.turn_risk !== "NONE" ? (s.head.turn_risk === "HIGH" ? "red" : "amber") : null) },
  { icon: "phone", label: "Phone", on: (s) => ((s.objects || {}).phone ? "red" : null), na: (s) => (s.objects || {}).phone == null },
  { icon: "cup", label: "Eating, drinking", on: (s) => ((s.objects || {}).consumption ? "amber" : null), na: (s) => (s.objects || {}).consumption == null },
  { icon: "smoke", label: "Smoking", on: (s) => ((s.objects || {}).cigarette ? "amber" : null), na: (s) => (s.objects || {}).cigarette == null },
  { icon: "belt", label: "Seatbelt off", on: (s) => ((s.objects || {}).seatbelt === "OFF" ? "red" : null), na: (s) => (s.objects || {}).seatbelt === "N/A" },
  { icon: "user", label: "Driver absent", on: (s) => (s.presence === "DRIVER_ABSENT" ? "red" : null) },
  { icon: "camera", label: "Camera blocked", on: (s) => (s.presence === "CAMERA_BLOCKED" ? "red" : null) },
];
function renderTelltales() {
  const list = $("telltales");
  if (list.children.length !== TELLTALES.length)
    list.replaceChildren(...TELLTALES.map((t) => { const li = el("li", "tt"); const lamp = el("span", "lamp"); lamp.append(icon(t.icon)); li.append(lamp, el("span", "tt-l", t.label)); return li; }));
  TELLTALES.forEach((t, i) => {
    const li = list.children[i], st = state.calibrating ? null : t.on(state), na = t.na && t.na(state);
    const cls = `tt${st ? ` lit ${st}` : ""}${na ? " na" : ""}`;
    if (li.className !== cls) {
      if (st && !li.classList.contains("lit")) { li.classList.add("blink"); setTimeout(() => li.classList.remove("blink"), 900); }
      li.className = cls + (li.classList.contains("blink") ? " blink" : "");
    }
    li.title = `${t.label}: ${na ? "not supported by the loaded model" : st === "red" ? "danger" : st === "amber" ? "warning" : "off"}`;
  });
}

/* The signal chain: every stage from the camera to the car, with its health. */
function renderChain() {
  const s = state, perf = s.perf || {}, links = s.links || {}, stages = perf.stages_ms || {}, req = s.requirements || {};
  const fresh = Date.now() - lastOk < 3000;
  const nodes = [
    { name: "Camera", value: perf.fps ? `${fmt(perf.fps, 1)} fps` : "—", tone: fresh && perf.fps ? "good" : "warn", note: perf.camera_fps ? `asks for ${perf.camera_fps}` : "" },
    { name: "Face mesh", value: stages.mediapipe != null ? `${fmt(stages.mediapipe, 0)} ms` : "—", tone: s.calibrating ? "info" : s.face_found ? "good" : "warn",
      note: s.calibrating ? "calibrating" : s.face_found ? "face tracked" : "no face" },
    { name: "Object detection", value: links.yolo === "running" ? (links.yolo_age != null ? `${fmt(links.yolo_age, 1)} s ago` : "running") : cap(links.yolo || "—"),
      tone: links.yolo === "running" ? "good" : links.yolo === "disabled" ? "info" : "warn", note: "phone, food, belt" },
    { name: "Cabin sensors", value: s.cabin ? (s.cabin.warm ? (s.cabin.mq3_rel != null ? `${fmt(s.cabin.mq3_rel, 1)}× air` : "Measuring") : "Warming up") : cap(links.uno || "—"),
      tone: links.uno === "connected" ? (s.cabin && s.cabin.warm ? "good" : "warn") : ["disabled", "unsupported"].includes(links.uno) ? "info" : "warn",
      note: s.cabin && !s.cabin.warm ? `${duration(s.cabin.warmup_left_s)} left` : "Arduino Uno" },
    { name: "Risk engine", value: perf.rate_hz != null ? `${fmt(perf.rate_hz, 1)} Hz` : "—",
      tone: perf.rate_hz == null ? "info" : perf.rate_hz >= (req.min_avg_rate_hz || 0) ? "good" : "crit", note: req.min_avg_rate_hz ? `needs ${req.min_avg_rate_hz} Hz` : "" },
    { name: "Voice", value: links.muted ? "Muted" : cap(links.voice || "—"), tone: links.muted ? "warn" : links.voice === "on" ? "good" : "info",
      note: links.voice_last_age != null ? `spoke ${duration(links.voice_last_age)} ago` : "nothing said yet" },
    { name: "Vehicle", value: links.vehicle ? (links.vehicle.estop ? "Stopped" : `${links.vehicle.speed_pct ?? "—"} %`) : cap(links.esp32 || "—"),
      tone: links.esp32 === "connected" ? (links.vehicle && links.vehicle.estop ? "crit" : "good") : ["disabled", "unsupported"].includes(links.esp32) ? "info" : "warn",
      note: links.vehicle ? "speed, ESP32" : "ESP32, Bluetooth" },
  ];
  const list = $("chain");
  if (list.children.length !== nodes.length)
    list.replaceChildren(...nodes.map(() => { const li = el("li", "node"); li.append(el("span", "n-dot"), el("span", "n-name"), el("span", "n-val"), el("span", "n-note")); return li; }));
  nodes.forEach((n, i) => {
    const li = list.children[i];
    li.className = `node ${n.tone}`;
    li.children[1].textContent = n.name; li.children[2].textContent = n.value; li.children[3].textContent = n.note;
  });
}

/* ---------- vehicle (ESP32 telemetry) */
const PULLOVER_SEC = 12;
function renderVehicle() {
  const links = state.links || {}, v = links.vehicle, box = $("p-vehicle");
  $("veh-sub").textContent = v ? "live from the ESP32" : "";
  if (!v) {
    box.replaceChildren(el("div", "veh-empty", links.esp32 === "connected"
      ? "ESP32 connected, but it sends no telemetry — flash the updated firmware (esp32/DriverGuardian_ESP32)."
      : `No telemetry — ESP32 link ${links.esp32 || "off"}.`));
    box.dataset.k = "";
    return;
  }
  const frag = document.createDocumentFragment();
  if (v.estop) frag.append(vehBanner("crit", "stop", v.estop === "obstacle" ? "Emergency stop — obstacle within 10 cm" : "Emergency stop — edge of the surface detected"));
  else if (v.risk === "HIGH" && v.pullover_s > 0) {
    const left = Math.max(0, PULLOVER_SEC - v.pullover_s), b = vehBanner("crit", "car", v.pullover_s >= PULLOVER_SEC ? "Pull-over finished — stopped" : `Pulling over to the right · stops in ${fmt(left, 1)} s`);
    const bar = el("div", "bar"), fill = el("i"); fill.style.width = `${Math.min(100, (v.pullover_s / PULLOVER_SEC) * 100)}%`; bar.append(fill); b.append(bar);
    frag.append(b);
  }
  if (v.link_failed) frag.append(vehBanner("warn", "bt", "The ESP32 lost the Pi's heartbeat — its fail-safe is active"));
  const grid = el("div", "veh-grid");
  const tile = (ic, k, val, sub, tone) => {
    const t = el("div", `vt ${tone || ""}`), kk = el("div", "k"); kk.append(icon(ic), document.createTextNode(k));
    t.append(kk, el("div", "v", val)); if (sub) t.append(el("div", "s", sub)); grid.append(t); return t;
  };
  const sp = tile("gauge", "Speed", v.estop ? "Stopped" : v.speed_pct == null ? "—" : `${v.speed_pct} %`,
    `left ${v.left_pwm}, right ${v.right_pwm} of ${v.base_pwm} PWM`);
  const meter = el("div", "meter"), mf = el("i"); mf.style.width = `${Math.min(100, v.speed_pct || 0)}%`; meter.append(mf); sp.append(meter);
  const dist = (k, d) => {
    const near = d != null && d <= 10, t = tile("ruler", k, d == null ? "Clear" : `${fmt(d, 0)} cm`, d == null ? "nothing within 1 m" : near ? "within the 10 cm stop distance" : "", near ? "crit" : "");
    const m = el("div", "meter dist"), f = el("i"); f.style.width = `${d == null ? 100 : Math.min(100, d)}%`;
    const th = el("b"); th.style.left = "10%"; th.title = "10 cm stop distance"; m.append(f, th); t.append(m);
  };
  dist("Front distance", v.front_cm);
  dist("Rear distance", v.rear_cm);
  const edge = v.ir_front || v.ir_rear;
  tile("edge", "Edge sensors", edge ? "Edge!" : "On surface", `front ${v.ir_front ? "at the edge" : "fine"}, rear ${v.ir_rear ? "at the edge" : "fine"}`, edge ? "crit" : "");
  frag.append(grid);
  box.replaceChildren(frag);
}
function vehBanner(tone, ic, text) {
  const b = el("div", `veh-banner ${tone}`); const t = el("div", "t"); t.append(icon(ic), document.createTextNode(text)); b.append(t); return b;
}

/* ---------- diagnostics drawer: a one-line summary while it is closed */
function renderDiagSummary() {
  const s = state, perf = s.perf || {}, req = s.requirements || {}, links = s.links || {}, out = $("diag-sum");
  const items = [];
  const add = (tone, text) => { const b = el("span", `status ${tone}`); b.append(icon(tone === "good" ? "check" : tone === "crit" ? "stop" : tone === "warn" ? "alert" : "info"), document.createTextNode(text)); items.push(b); };
  if (perf.rate_hz != null) add(perf.rate_hz >= req.min_avg_rate_hz ? "good" : "crit", `${fmt(perf.rate_hz, 1)} Hz`);
  if (perf.gap_session_ms != null) add(perf.gap_session_ms <= req.max_gap_ms ? "good" : "crit", `gap ${Math.round(perf.gap_session_ms)} ms`);
  if (s.system && s.system.temp_c != null) add((s.system.throttled || []).length || s.system.temp_c >= 80 ? "crit" : s.system.temp_c >= 70 ? "warn" : "good", `${fmt(s.system.temp_c, 0)} °C`);
  add(links.yolo === "running" ? "good" : ["disabled"].includes(links.yolo) ? "neutral" : "warn", `YOLO ${links.yolo || "—"}`);
  add(links.esp32 === "connected" ? "good" : ["disabled", "unsupported"].includes(links.esp32) ? "neutral" : "warn", `ESP32 ${links.esp32 || "—"}`);
  out.replaceChildren(...items);
}
const diag = $("diag");
diag.open = store.get("dg-diag", "0") === "1";
diag.addEventListener("toggle", () => { store.set("dg-diag", diag.open ? "1" : "0"); if (diag.open && state) renderPanels(); });

/* ---------- tests run from the dashboard */
let testSeq = null, testResultTs = undefined;
function renderTest() {
  const t = state.test || {}, ov = $("test-ov");
  if (testResultTs === undefined) testResultTs = t.result ? t.result.ts : null;   // don't pop up old results on load
  ov.hidden = !t.active;
  if (t.active) {
    $("to-title").textContent = t.title;
    $("to-step").textContent = t.step || t.params || "";
    setAnimated($("to-instr"), t.instruction || "");
    $("to-count").textContent = t.remaining != null && t.phase !== "analyse" ? String(Math.ceil(t.remaining)) : "";
    $("to-sees").textContent = t.sees ? `App sees: ${t.sees}` : "";
    $("to-bar").style.width = `${Math.round((t.progress || 0) * 100)}%`;
    ov.classList.toggle("go", !!t.show);
    ov.classList.toggle("closed-eyes", !!t.eyes_closed_step);
    ov.classList.toggle("busy", t.phase === "analyse" || t.phase === "calibrate");
    if (testSeq !== null && t.seq !== testSeq) beep(1, t.show ? 1320 : 988);
  }
  testSeq = t.seq;
  if (t.result && t.result.ts !== testResultTs) {
    testResultTs = t.result.ts;
    showTestResult(t.result);
  }
}
function showTestResult(res) {
  $("rd-title").textContent = res.aborted ? `${res.title} — stopped` : `${res.title} — ${res.passed ? "PASS" : "FAIL"}`;
  $("rd-body").replaceChildren(testResultNode(res));
  const d = $("res-dlg"); if (!d.open) d.showModal();
}
function verdict(ok, text) { return statusBadge(ok, text || (ok ? "PASS" : "FAIL")); }
const pct1 = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)} %`);
function testResultNode(res) {
  const wrap = el("div", "test-res");
  const meta = res.test === "face" ? `${res.rounds_done || res.rounds} of ${res.rounds} round${res.rounds > 1 ? "s" : ""} in “${res.condition}” conditions, ${res.frames} frames`
    : `${(res.trials || []).length} trial${(res.trials || []).length === 1 ? "" : "s"} with a ${res.object}`;
  wrap.append(el("div", "tr-meta", `${dateLabel(res.ts)}. ${meta}.${res.aborted ? ` Stopped: ${res.aborted}.` : ""}`));
  const kv = el("div", "kv");
  if (res.test === "face") {
    const e = res.eye || {}, y = res.yawn || {};
    kvRow(kv, "eye", `Eye state, balanced accuracy (≥ ${Math.round((res.requirement || 0.9) * 100)} %)`, verdict(e.pass, pct1(e.balanced)));
    kvRow(kv, "eyeOff", "Closed eyes detected", `${e.tp} / ${e.closed_frames} frames`, pct1(e.closed_recall));
    kvRow(kv, "eye", "Open eyes correct", `${e.tn} / ${e.open_frames} frames`, pct1(e.open_recall));
    kvRow(kv, "mouth", `Yawning, event accuracy (≥ ${Math.round((res.requirement || 0.9) * 100)} %)`, verdict(y.pass, pct1(y.accuracy)));
    kvRow(kv, "mouth", "Yawns detected", `${y.hits} / ${y.steps}`);
    kvRow(kv, "alert", "False yawns", `${y.false} / ${y.other_steps} steps`, y.talk_steps ? `talking ${y.talk_false}/${y.talk_steps}` : "");
    kvRow(kv, "user", "Face found", pct1(res.face_found), res.low_light ? `low light ${pct1(res.low_light)}` : "");
    wrap.append(kv);
    if (y.steps < 10) wrap.append(el("p", "tr-note", `Only ${y.steps} yawn${y.steps === 1 ? "" : "s"} in this run — combine several runs before quoting the yawn figure.`));
  } else {
    kvRow(kv, "timer", `Longest delay (≤ ${fmt(res.limit, 1)} s)`, res.max == null ? statusBadge(false, "", "not measured") : verdict(res.pass, `${fmt(res.max, 2)} s`));
    kvRow(kv, "clock", "Mean, median", res.mean == null ? "—" : `${fmt(res.mean, 2)} s, ${fmt(res.median, 2)} s`);
    kvRow(kv, "check", "Trials measured", `${res.measured} / ${res.trials_n}`, res.missed ? `${res.missed} never confirmed` : "");
    wrap.append(kv);
    const tw = el("div", "table-wrap");
    renderTable(tw, ["Trial", "Visible after tone", "Confirmed after tone", "Delay"],
      (res.trials || []).map((t) => [String(t.n), t.onset == null ? "never" : `${fmt(t.onset, 2)} s`, t.confirmed == null ? "never" : `${fmt(t.confirmed, 2)} s`, t.delay == null ? "—" : `${fmt(t.delay, 2)} s`]));
    wrap.append(tw);
  }
  return wrap;
}
const testDlg = $("test-dlg"), testForm = $("td-form");
testForm.querySelectorAll('input[name="test"]').forEach((r) => r.addEventListener("change", () => {
  testForm.querySelectorAll(".td-pane").forEach((p) => { p.hidden = p.dataset.for !== testForm.test.value; });
}));
async function openTests() {
  if (!state) return;
  if (state.test && state.test.active) {
    if (await dialog({ title: "Stop the test?", body: "What was recorded so far is scored and saved.", confirm: "Stop test", danger: true }))
      control("test_stop", {}, "Test stopped");
    return;
  }
  testDlg.returnValue = "";
  testDlg.showModal();
  testDlg.onclose = () => {
    if (testDlg.returnValue !== "ok") return;
    const f = testForm, test = f.test.value;
    const params = test === "face" ? { test, rounds: Number(f.rounds.value), condition: f.condition.value.trim() || "normal" }
      : { test, object: f.object.value, trials: Number(f.trials.value) };
    control("test_start", params, test === "face" ? "Face test starting — calibrating first" : "Detection-delay test starting");
  };
}
$("btn-test").onclick = openTests;
$("to-stop").onclick = () => control("test_stop", {}, "Test stopped");

/* ---------------- panels */
function statusBadge(ok, text, neutral) {
  const tone = neutral ? "neutral" : ok ? "good" : "crit";
  const s = el("span", `status ${tone}`);
  s.append(icon(neutral ? "info" : ok ? "check" : "stop"), document.createTextNode(neutral || text));
  return s;
}
function kvRow(parent, iconName, label, valueNode, small) {
  const k = el("div", "k"); k.append(icon(iconName), document.createTextNode(label));
  const v = el("div", "v");
  if (typeof valueNode === "string") v.textContent = valueNode; else v.append(valueNode);
  if (small) v.append(el("small", null, small));
  parent.append(k, v);
}
function riskStack(timeIn, withLegend = true) {
  const frag = document.createDocumentFragment();
  const tin = timeIn || {};
  const tot = RISK_ORDER.reduce((a, r) => a + (tin[r] || 0), 0);
  const stack = el("div", "stack");
  stack.setAttribute("role", "img");
  stack.setAttribute("aria-label", RISK_ORDER.map((r) => `${lv(r).word} ${tot ? Math.round((tin[r] || 0) / tot * 100) : 0}%`).join(", "));
  const legend = el("div", "stack-legend");
  RISK_ORDER.forEach((r) => {
    const share = tot ? (tin[r] || 0) / tot : 0;
    if (share > 0) {
      const seg = el("i"); seg.style.width = `${share * 100}%`; seg.style.background = `var(${lv(r).token})`;
      seg.title = `${lv(r).word}: ${duration(tin[r])} (${Math.round(share * 100)}%)`;
      stack.append(seg);
    }
    const k = el("div", "k"); const ic = icon(lv(r).icon); ic.style.color = `var(${lv(r).token})`;
    k.append(ic, document.createTextNode(lv(r).word), el("b", null, `${Math.round(share * 100)}%`));
    legend.append(k);
  });
  frag.append(stack);
  if (withLegend) frag.append(legend);
  return frag;
}
const STAGE_NAMES = { camera: "Camera (incl. waiting for frame)", preprocess: "Pre-processing", mediapipe: "Face mesh",
  presence_logic: "Presence & timers", yolo: "YOLO hand-off", risk_draw: "Risk & overlay", imshow: "Local window", waitkey: "Window events" };

function renderPanels() {
  const s = state, perf = s.perf || {}, req = s.requirements || {}, sys = s.system, links = s.links || {};
  const pr = $("p-req"); pr.replaceChildren();
  const kv = el("div", "kv");
  const rate = perf.rate_hz, gap = perf.gap_session_ms;
  kvRow(kv, "gauge", `Average update rate (≥ ${req.min_avg_rate_hz} Hz)`, rate == null ? statusBadge(false, "", "measuring…") : statusBadge(rate >= req.min_avg_rate_hz, `${fmt(rate, 1)} Hz`));
  kvRow(kv, "clock", `Longest gap this session (≤ ${Math.round(req.max_gap_ms)} ms)`, gap == null ? statusBadge(false, "", "measuring…") : statusBadge(gap <= req.max_gap_ms, `${Math.round(gap)} ms`));
  kvRow(kv, "bolt", "Processing rate", `${fmt(perf.fps, 1)} FPS`, perf.camera_fps ? `camera ${perf.camera_fps}` : "");
  pr.append(kv);
  const stages = perf.stages_ms || {}, names = Object.keys(stages);
  if (names.length) {
    pr.append(el("hr", "sep"), el("div", "sub-h", "Time per frame"));
    const total = names.reduce((a, k) => a + stages[k], 0) || 1, bars = el("div", "bars");
    names.forEach((k) => {
      const track = el("div", "track"), fill = el("div", "fill");
      fill.style.width = `${Math.max(0.5, (stages[k] / total) * 100)}%`; track.append(fill);
      bars.append(el("div", "n", STAGE_NAMES[k] || k), track, el("div", "val", `${fmt(stages[k], 1)} ms`));
    });
    pr.append(bars);
  }

  const ps = $("p-sys"); ps.replaceChildren();
  const kv2 = el("div", "kv");
  if (sys) {
    const t = sys.temp_c, thr = (sys.throttled || []).length > 0;
    if (t != null) {
      const tone = thr || t >= 80 ? "crit" : t >= 70 ? "warn" : "good";
      const b = el("span", `status ${tone}`);
      b.append(icon(tone === "good" ? "check" : tone === "warn" ? "alert" : "stop"), document.createTextNode(`${fmt(t, 1)} °C${thr ? ", throttling" : ""}`));
      kvRow(kv2, "temp", "CPU temperature", b);
    }
    if (sys.load1 != null) kvRow(kv2, "cpu", "CPU load", `${fmt(sys.load1, 2)}`, `of ${sys.cores} cores`);
    if (sys.mem_available_mb != null) kvRow(kv2, "memory", "Memory available", `${fmt(sys.mem_available_mb / 1024, 1)} GB`, sys.swap_used_mb > 50 ? `swap ${Math.round(sys.swap_used_mb)} MB` : "");
    if (sys.rss_mb != null) kvRow(kv2, "box", "App memory", `${Math.round(sys.rss_mb)} MB`, `${sys.threads} threads`);
  } else kv2.append(el("div", "k", "System readings appear on the Raspberry Pi"), el("div", "v", ""));
  ps.append(kv2, el("hr", "sep"), el("div", "sub-h", "Components"));
  const kv3 = el("div", "kv");
  const comp = (v, good) => {
    const tone = v === good ? "good" : ["disabled", "off", "unsupported"].includes(v) ? "neutral" : "warn";
    const b = el("span", `status ${tone}`);
    b.append(icon(tone === "good" ? "check" : tone === "warn" ? "alert" : "info"), document.createTextNode(cap(v || "—")));
    return b;
  };
  kvRow(kv3, "box", "Object detection (YOLO)", comp(links.yolo, "running"), links.yolo_age != null && links.yolo === "running" ? `${fmt(links.yolo_age, 1)} s ago` : "");
  kvRow(kv3, "bt", "ESP32 link", comp(links.esp32, "connected"));
  kvRow(kv3, links.muted ? "mute" : "voice", "Voice alerts", comp(links.muted ? "muted" : links.voice, "on"));
  if (links.voice_last) {
    const q = el("div", "quote", `“${links.voice_last}”`);
    if (links.voice_last_age != null) q.append(el("small", null, `${duration(links.voice_last_age)} ago`));
    kv3.append(q);
  }
  kvRow(kv3, "users", "Dashboard viewers", String(s.viewers != null ? s.viewers : 0));
  ps.append(kv3);

  const pn = $("p-session"); pn.replaceChildren();
  const sess = s.session || {};
  if (sess.started_ts) $("session-start").textContent = `since ${clock(sess.started_ts, false)}`;
  pn.append(el("div", "big", duration(sess.uptime_s)), el("div", "sub-h", "Time by risk level"), riskStack(sess.time_in));
  const alerts = Object.entries(sess.alerts || {}).sort((a, b) => b[1] - a[1]);
  pn.append(el("hr", "sep"), el("div", "sub-h", "Alerts by type"));
  if (alerts.length) {
    const list = el("div", "count-list");
    alerts.forEach(([c, n]) => list.append(el("span", null, caseName(c)), el("b", null, String(n))));
    pn.append(list);
  } else pn.append(el("div", "k", "No alerts yet"));
  if (s.baseline) {
    pn.append(el("hr", "sep"), el("div", "sub-h", "Calibrated baseline"));
    const kb = el("div", "kv");
    kvRow(kb, "eye", "Eye openness (EAR)", fmt(s.baseline.ear, 3));
    kvRow(kb, "mouth", "Mouth opening (MAR)", fmt(s.baseline.mar, 3));
    pn.append(kb);
  }
}

/* ================================================================ charts */
function niceTicks(min, max, count = 4) {
  if (min === max) { min -= 1; max += 1; }
  const span = max - min, step0 = span / count, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count + 0.5) || mag * 10;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, ticks = [];
  for (let v = lo; v <= hi + step * 0.001; v += step) ticks.push(+v.toFixed(10));
  return { lo, hi, ticks, step };
}
function xTicks(src, width = 600) {
  const { t0, t1, clockAxis } = src, span = t1 - t0, out = [];
  if (!clockAxis) {
    const step = span <= 60 ? 15 : span <= 300 ? 60 : 120;
    for (let back = 0; back <= span + 0.01; back += step) out.push({ t: t1 - back, label: back === 0 ? "now" : step < 60 ? `−${back}s` : `−${back / 60}m` });
    return out;
  }
  const maxTicks = Math.max(2, Math.min(6, Math.floor(width / 85)));   // HH:MM:SS needs ~70 px
  const step = [10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200].find((s) => span / s <= maxTicks) || 7200;
  for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) out.push({ t, label: clock(t, step < 60) });
  return out;
}
const tip = $("tip");
function showTip(card, px, py, title, rows) {
  tip.replaceChildren(el("div", "t", title));
  rows.forEach(([key, value, label]) => {
    const r = el("div", "r");
    if (key) { const k = el("span", "line-key"); k.style.background = key; r.append(k); }
    r.append(el("b", null, value), el("span", null, label));
    tip.append(r);
  });
  tip.style.display = "block";
  const rect = card.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
  let x = rect.left + window.scrollX + px + 14, y = rect.top + window.scrollY + py - th - 10;
  if (x + tw > window.scrollX + document.documentElement.clientWidth - 8) x = rect.left + window.scrollX + px - tw - 14;
  if (y < window.scrollY + 8) y = rect.top + window.scrollY + py + 14;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
function hideTip() { tip.style.display = "none"; }

function chartShell(card, title, sub, legendItems) {
  card.replaceChildren();
  const head = el("div", "card-h");
  head.append(el("h2", null, title));
  if (sub) head.append(el("span", "sub", sub));
  head.append(el("span", "spacer"));
  const tbtn = el("button", "table-toggle", "Table");
  tbtn.setAttribute("aria-pressed", "false");
  head.append(tbtn);
  card.append(head);
  if (legendItems) {
    const lg = el("div", "legend");
    legendItems.forEach((it) => {
      const k = el("span", "k");
      if (it.icon) { const ic = icon(it.icon); ic.style.color = `var(${it.token})`; k.append(ic); }
      else { const key = el("span", it.rect ? "rect-key" : "line-key"); key.style.background = `var(${it.token})`; k.append(key); }
      k.append(document.createTextNode(it.label));
      lg.append(k);
    });
    card.append(lg);
  }
  const body = el("div", "card-b"), plot = el("div", "chart"), tableWrap = el("div", "table-wrap");
  tableWrap.hidden = true;
  body.append(plot, tableWrap);
  card.append(body);
  const shell = { plot, tableWrap, showTable: false };
  tbtn.onclick = () => {
    shell.showTable = !shell.showTable;
    tbtn.setAttribute("aria-pressed", String(shell.showTable));
    tbtn.textContent = shell.showTable ? "Chart" : "Table";
    plot.hidden = shell.showTable; tableWrap.hidden = !shell.showTable;
    shell.onToggle && shell.onToggle();
  };
  return shell;
}
function renderTable(wrap, headers, rows) {
  const t = el("table", "data"), thead = el("thead"), tr = el("tr");
  headers.forEach((h) => tr.append(el("th", null, h)));
  thead.append(tr);
  const tb = el("tbody");
  rows.forEach((r) => { const row = el("tr"); r.forEach((c) => row.append(el("td", null, c))); tb.append(row); });
  t.append(thead, tb);
  wrap.replaceChildren(t);
}
function attachHover(svg, card, hit, opts) {
  // opts: { count, at(i) -> {x, t, rows, title}, nearest(evt) -> i, hover <g>, onShow(t), onClear(), onClick(i) }
  let idx = null;
  const show = (i) => {
    if (!opts.count()) return;
    idx = Math.max(0, Math.min(opts.count() - 1, i));
    const r = opts.at(idx);
    const svgRect = svg.getBoundingClientRect(), cardRect = card.getBoundingClientRect(), W = +svg.getAttribute("data-w");
    showTip(card, (svgRect.left - cardRect.left) + r.x * (svgRect.width / W), (svgRect.top - cardRect.top) + 18, r.title, r.rows);
    if (opts.onShow && r.t != null) opts.onShow(r.t);
  };
  const clear = () => { idx = null; opts.hover.replaceChildren(); hideTip(); if (opts.onClear) opts.onClear(); };
  if (opts.onClick) {
    hit.style.cursor = "pointer";
    hit.addEventListener("click", (e) => opts.onClick(opts.nearest(e)));
    hit.addEventListener("keydown", (e) => { if (e.key === "Enter" && idx != null) opts.onClick(idx); });
  }
  hit.addEventListener("pointermove", (e) => show(opts.nearest(e)));
  hit.addEventListener("pointerleave", clear);
  hit.addEventListener("focus", () => show(opts.count() - 1));
  hit.addEventListener("blur", clear);
  hit.addEventListener("keydown", (e) => {
    const n = opts.count();
    if (e.key === "ArrowLeft") { show((idx ?? n - 1) - (e.shiftKey ? 20 : 1)); e.preventDefault(); }
    if (e.key === "ArrowRight") { show((idx ?? n - 1) + (e.shiftKey ? 20 : 1)); e.preventDefault(); }
    if (e.key === "Escape") hit.blur();
  });
}

/* Charts in one group share the hover: pointing at a time on one chart
   shows the same moment on the others. */
function syncGroup() {
  const members = [];
  return {
    add(m) { members.push(m); },
    show(from, t) { members.forEach((m) => m !== from && m.showT(t)); },
    clear(from) { members.forEach((m) => m !== from && m.clearT()); },
  };
}

/* Line chart (one y-axis, shared unit). source() -> {rows, t0, t1, clockAxis, gap, label} */
function lineChart(card, cfg, source, opts = {}) {
  let cur = null;   // the current render's geometry, for synced hover
  const shell = chartShell(card, cfg.title, cfg.sub, cfg.series.length > 1 ? cfg.series.map((s) => ({ token: s.token, label: s.label })) : null);
  const H = 170, pad = { l: 40, r: cfg.series.length > 1 ? 44 : 14, t: 10, b: 24 };
  function render() {
    const src = source(), { rows, t0, t1 } = src;
    if (shell.showTable) {
      const recent = rows.slice(-60).reverse();
      renderTable(shell.tableWrap, ["Time", ...cfg.series.map((s) => `${s.label}${cfg.unit ? ` (${cfg.unit})` : ""}`), ...(cfg.ref ? [cfg.ref.label] : [])],
        recent.map((r) => [clock(r.ts), ...cfg.series.map((s) => fmt(r[s.key], cfg.digits)), ...(cfg.ref ? [fmt(r[cfg.ref.key], cfg.digits)] : [])]));
      return;
    }
    const W = shell.plot.clientWidth || 300;
    const vals = [];
    rows.forEach((r) => { cfg.series.forEach((s) => { if (r[s.key] != null) vals.push(r[s.key]); }); if (cfg.ref && r[cfg.ref.key] != null) vals.push(r[cfg.ref.key]); });
    if (cfg.includeZero) vals.push(0);
    if (!rows.length || vals.length <= (cfg.includeZero ? 1 : 0)) { shell.plot.replaceChildren(el("div", "empty", cfg.emptyText || "No data yet — waiting for the driver's face")); return; }
    let min = Math.min(...vals), max = Math.max(...vals);
    if (cfg.minSpan && max - min < cfg.minSpan) { const c = (max + min) / 2; min = c - cfg.minSpan / 2; max = c + cfg.minSpan / 2; }
    if (cfg.floor != null && min < cfg.floor) { max += cfg.floor - min; min = cfg.floor; }
    const yt = niceTicks(min, max, 4);
    if (cfg.floor != null && yt.lo < cfg.floor) { yt.ticks = yt.ticks.filter((v) => v >= cfg.floor); yt.lo = cfg.floor; }
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const x = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * pw;
    const y = (v) => pad.t + (1 - (v - yt.lo) / (yt.hi - yt.lo)) * ph;
    const svg = svgEl("svg", { class: "plot", viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "data-w": W, "aria-label": `${cfg.title} — ${src.label}` });
    yt.ticks.forEach((v) => {
      svg.append(svgEl("line", { class: v === 0 && cfg.includeZero ? "baseline" : "gridline", x1: pad.l, x2: W - pad.r, y1: y(v), y2: y(v) }));
      const tx = svgEl("text", { class: "tick", x: pad.l - 6, y: y(v) + 3.5, "text-anchor": "end" });
      tx.textContent = Math.abs(yt.step) < 1 ? v.toFixed(2) : String(Math.round(v)); svg.append(tx);
    });
    svg.append(svgEl("line", { class: "baseline", x1: pad.l, x2: W - pad.r, y1: pad.t + ph, y2: pad.t + ph }));
    xTicks(src, W).forEach((tk) => {
      const tx = svgEl("text", { class: "tick", x: x(tk.t), y: H - 6, "text-anchor": tk.label === "now" ? "end" : "middle" });
      tx.textContent = tk.label; svg.append(tx);
    });
    const pathFor = (key) => {
      let d = "", prevT = null;
      rows.forEach((r) => {
        const v = r[key];
        if (v == null) { prevT = null; return; }
        d += (prevT == null || r.t - prevT > src.gap ? "M" : "L") + x(r.t).toFixed(1) + "," + y(v).toFixed(1);
        prevT = r.t;
      });
      return d;
    };
    if (cfg.ref) {
      const d = pathFor(cfg.ref.key);
      if (d) {
        svg.append(svgEl("path", { d, class: "ref", fill: "none" }));
        const last = [...rows].reverse().find((r) => r[cfg.ref.key] != null);
        if (last) {
          const lbl = svgEl("text", { class: "ref-label", x: W - pad.r, y: y(last[cfg.ref.key]) - 5, "text-anchor": "end" });
          lbl.textContent = `${cfg.ref.label} ${fmt(last[cfg.ref.key], cfg.digits)}${cfg.ref.unit || ""}`; svg.append(lbl);
        }
      }
    }
    const endYs = [];
    cfg.series.forEach((s) => {
      svg.append(svgEl("path", { d: pathFor(s.key), class: "line", style: `stroke:var(${s.token})` }));
      const last = [...rows].reverse().find((r) => r[s.key] != null);
      if (last && cfg.series.length > 1) endYs.push({ s, yy: y(last[s.key]) });
    });
    if (endYs.length === 2 && Math.abs(endYs[0].yy - endYs[1].yy) >= 13)
      endYs.forEach(({ s, yy }) => { const t = svgEl("text", { class: "end-label", x: W - pad.r + 6, y: yy + 4 }); t.textContent = s.short || s.label; svg.append(t); });
    const hover = svgEl("g", {}); svg.append(hover);
    const hit = svgEl("rect", { x: pad.l, y: pad.t, width: pw, height: ph, fill: "transparent", tabindex: "0",
      "aria-label": `${cfg.title} chart: use left and right arrow keys to read values` });
    svg.append(hit);
    const nearestT = (t) => {
      let lo = 0, hi = rows.length - 1;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (rows[mid].t < t) lo = mid + 1; else hi = mid; }
      if (lo > 0 && Math.abs(rows[lo - 1].t - t) < Math.abs(rows[lo].t - t)) lo--;
      return lo;
    };
    const draw = (i) => {
      const r = rows[i], cx = x(r.t);
      hover.replaceChildren(svgEl("line", { class: "xhair", x1: cx, x2: cx, y1: pad.t, y2: pad.t + ph }));
      cfg.series.forEach((s) => {
        if (r[s.key] != null) hover.append(svgEl("circle", { class: "hover-dot", cx, cy: y(r[s.key]), r: 4, style: `fill:var(${s.token})` }));
      });
      return r;
    };
    cur = { hover, draw, nearestT, t0, t1, n: rows.length };
    attachHover(svg, card, hit, {
      hover, count: () => rows.length,
      nearest: (evt) => {
        const rect = svg.getBoundingClientRect(), px = (evt.clientX - rect.left) * (W / rect.width);
        return nearestT(t0 + ((px - pad.l) / pw) * (t1 - t0));
      },
      at: (i) => {
        const r = draw(i), tipRows = [];
        cfg.series.forEach((s) => tipRows.push([`var(${s.token})`, r[s.key] == null ? "—" : `${fmt(r[s.key], cfg.digits)}${cfg.unit ? " " + cfg.unit : ""}`, s.label]));
        if (cfg.ref && r[cfg.ref.key] != null) tipRows.push(["var(--muted)", fmt(r[cfg.ref.key], cfg.digits), cfg.ref.label]);
        return { x: x(r.t), t: r.t, title: clock(r.ts), rows: tipRows };
      },
      onShow: opts.group && ((t) => opts.group.show(self, t)),
      onClear: opts.group && (() => opts.group.clear(self)),
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  const self = {
    render,
    showT(t) { if (cur && cur.n && !shell.showTable && t >= cur.t0 && t <= cur.t1) cur.draw(cur.nearestT(t)); else this.clearT(); },
    clearT() { if (cur) cur.hover.replaceChildren(); },
  };
  if (opts.group) opts.group.add(self);
  return self;
}

/* Risk timeline: status-coloured segments + marker flags. */
function riskChart(card, source, opts = {}) {
  const shell = chartShell(card, "Risk timeline", opts.onPick ? "click a stretch to see its events" : "",
    RISK_ORDER.map((r) => ({ icon: lv(r).icon, token: lv(r).token, label: lv(r).word })));
  let cur = null;
  const H = 78, pad = { l: 14, r: 14, t: 22, b: 24 };
  function segments(rows, step, gap) {
    const segs = [];
    rows.forEach((r) => {
      const last = segs[segs.length - 1];
      if (last && last.risk === r.risk && last.case === r.case && r.t - last.end <= gap) last.end = r.t;
      else segs.push({ risk: r.risk, case: r.case, start: r.t, end: r.t, ts: r.ts });
    });
    segs.forEach((s) => { s.end += step; });
    return segs;
  }
  function render() {
    const src = source(), { rows, t0, t1 } = src;
    const segs = segments(rows, src.step, src.gap);
    const markers = src.markers || [];
    if (shell.showTable) {
      renderTable(shell.tableWrap, ["Started", "Duration", "Level", "Reason"],
        segs.slice().reverse().slice(0, 100).map((s) => [clock(s.ts), duration(s.end - s.start), lv(s.risk).word, caseName(s.case)]));
      return;
    }
    if (!rows.length) { shell.plot.replaceChildren(el("div", "empty", "No data yet")); return; }
    const W = shell.plot.clientWidth || 300, pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const x = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * pw;
    const svg = svgEl("svg", { class: "plot", viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "data-w": W, "aria-label": `Risk timeline — ${src.label}` });
    svg.append(svgEl("rect", { x: pad.l, y: pad.t, width: pw, height: ph, rx: 4, style: "fill:var(--surface-2)" }));
    segs.forEach((s) => {
      let x0 = x(s.start), x1 = x(s.end);
      if (x1 - x0 > 3) { x0 += 1; x1 -= 1; }   // 2px surface gap between neighbours
      svg.append(svgEl("rect", { x: x0, y: pad.t, width: Math.max(1, x1 - x0), height: ph, rx: 3, style: `fill:var(${lv(s.risk).token})` }));
    });
    markers.filter((m) => m.t >= t0 && m.t <= t1).forEach((m) => {
      const mx = x(m.t);
      svg.append(svgEl("line", { class: "marker-tick", x1: mx, x2: mx, y1: 6, y2: pad.t + ph }));
      svg.append(svgEl("path", { class: "marker-head", d: `M${mx},4 l6,3.5 l-6,3.5 z` }));
    });
    xTicks(src, W).forEach((tk) => {
      const tx = svgEl("text", { class: "tick", x: x(tk.t), y: H - 6, "text-anchor": tk.label === "now" ? "end" : "middle" });
      tx.textContent = tk.label; svg.append(tx);
    });
    const hover = svgEl("g", {}); svg.append(hover);
    const hit = svgEl("rect", { x: pad.l, y: 0, width: pw, height: pad.t + ph + 4, fill: "transparent", tabindex: "0",
      "aria-label": "Risk timeline: use left and right arrow keys to step through segments" + (opts.onPick ? ", Enter to show its events" : "") });
    svg.append(hit);
    cur = { hover, x, t0, t1, top: pad.t - 2, bottom: pad.t + ph + 2 };
    attachHover(svg, card, hit, {
      hover, count: () => segs.length,
      onShow: opts.group && ((t) => opts.group.show(self, t)),
      onClear: opts.group && (() => opts.group.clear(self)),
      onClick: opts.onPick && ((i) => { const sg = segs[Math.max(0, Math.min(segs.length - 1, i))]; if (sg) opts.onPick(sg.ts, sg.ts + (sg.end - sg.start)); }),
      nearest: (evt) => {
        const rect = svg.getBoundingClientRect(), px = (evt.clientX - rect.left) * (W / rect.width), t = t0 + ((px - pad.l) / pw) * (t1 - t0);
        const i = segs.findIndex((s) => t <= s.end);
        return i < 0 ? segs.length - 1 : i;
      },
      at: (i) => {
        const s = segs[i];
        hover.replaceChildren(svgEl("rect", { x: x(s.start), y: pad.t - 2, width: Math.max(2, x(s.end) - x(s.start)), height: ph + 4, rx: 4, fill: "none", style: "stroke:var(--ink);stroke-width:1.5" }));
        const rowsTip = [[`var(${lv(s.risk).token})`, lv(s.risk).word, caseName(s.case)]];
        markers.filter((m) => m.t >= s.start && m.t <= s.end).slice(0, 3).forEach((m) => rowsTip.push(["var(--ink)", "Marker", m.title]));
        return { x: (x(s.start) + x(s.end)) / 2, t: (s.start + s.end) / 2, title: `${clock(s.ts)}, for ${duration(s.end - s.start)}`, rows: rowsTip };
      },
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  const self = {
    render,
    showT(t) {
      if (!cur || shell.showTable || t < cur.t0 || t > cur.t1) { this.clearT(); return; }
      const cx = cur.x(t);
      cur.hover.replaceChildren(svgEl("line", { class: "xhair", x1: cx, x2: cx, y1: cur.top, y2: cur.bottom }));
    },
    clearT() { if (cur) cur.hover.replaceChildren(); },
  };
  if (opts.group) opts.group.add(self);
  return self;
}

const EAR_CFG = { title: "Eye openness", sub: "eye aspect ratio (EAR)", digits: 3, minSpan: 0.1, floor: 0,
  series: [{ key: "ear", label: "EAR", token: "--series-1" }], ref: { key: "ear_thr", label: "closed below" } };
const MAR_CFG = { title: "Mouth opening", sub: "mouth aspect ratio (MAR)", digits: 3, minSpan: 0.1, floor: 0,
  series: [{ key: "mar", label: "MAR", token: "--series-1" }], ref: { key: "mar_thr", label: "open above" } };
const HEAD_CFG = { title: "Head pose", sub: "change from calibrated position", unit: "°", digits: 1, includeZero: true, minSpan: 20,
  series: [{ key: "pitch", label: "Pitch (down +)", short: "Pitch", token: "--series-1" }, { key: "yaw", label: "Yaw (right +)", short: "Yaw", token: "--series-2" }] };

/* ================================================================ fatigue */
const PERCLOS_CFG = { title: "Eyes closed (PERCLOS)", sub: "% of the last minute", unit: "%", digits: 0,
  includeZero: true, minSpan: 20, floor: 0, emptyText: "Appears after 20 s of face tracking",
  series: [{ key: "perclos_pct", label: "PERCLOS", token: "--series-1" }], ref: { key: "perclos_ref", label: "drowsy above", unit: " %" } };
const BLINK_CFG = { title: "Blink rate", sub: "per minute", unit: "/min", digits: 0,
  includeZero: true, minSpan: 20, floor: 0, emptyText: "Appears after 30 s of face tracking",
  series: [{ key: "blink_rate", label: "Blinks per minute", token: "--series-1" }] };
const PERCLOS_DROWSY = 15;          // % - the usual PERCLOS drowsiness threshold

/* Per-row fatigue measures from the saved counters. Counters restart at a
   recalibration, so only increases are counted. Cached per sample array. */
const fatigueCache = new WeakMap();
function deriveFatigue(rows) {
  const c = fatigueCache.get(rows);
  if (c && c.n === rows.length) return c.out;
  const out = new Array(rows.length), adjB = new Array(rows.length), adjY = new Array(rows.length);
  let b = 0, y = 0, pb = null, py = null, j = 0;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    if (r.blinks != null) { if (pb != null && r.blinks > pb) b += r.blinks - pb; pb = r.blinks; }
    if (r.yawns != null) { if (py != null && r.yawns > py) y += r.yawns - py; py = r.yawns; }
    adjB[i] = b; adjY[i] = y;
    while (j < i && rows[j].t < r.t - 60) j++;
    const span = r.t - rows[j].t;
    out[i] = { ...r, perclos_pct: r.perclos == null ? null : r.perclos * 100, perclos_ref: r.perclos == null ? null : PERCLOS_DROWSY,
               blink_rate: r.blinks == null || span < 30 ? null : ((adjB[i] - adjB[j]) / span) * 60, _yawns: adjY[i] };
  }
  fatigueCache.set(rows, { n: rows.length, out });
  return out;
}
function withFatigue(source, base) {
  return () => {
    const src = source(), all = deriveFatigue(base ? base() : src.rows);
    return { ...src, rows: base ? all.slice(all.length - src.rows.length) : all };
  };
}
/* Fatigue at a glance: PERCLOS, blink rate, yawns, longest eye closure. */
function fatigueCard(card, source) {
  function render() {
    const src = source(), rows = src.rows;
    card.replaceChildren();
    const h = el("div", "card-h"); h.append(el("h2", null, "Fatigue summary"), el("span", "sub", src.label));
    const b = el("div", "card-b");
    card.append(h, b);
    if (!rows.length || rows.every((r) => r.perclos == null && r.blinks == null)) { b.append(el("div", "empty", "Appears once the driver's face is tracked")); return; }
    const pc = rows.map((r) => r.perclos_pct).filter((v) => v != null), br = rows.map((r) => r.blink_rate).filter((v) => v != null);
    const now = [...rows].reverse().find((r) => r.perclos_pct != null);
    const peak = pc.length ? Math.max(...pc) : null;
    const tone = (v) => (v == null ? null : v >= 30 ? "crit" : v >= PERCLOS_DROWSY ? "warn" : "good");
    const badge = (v, text) => { const t = tone(v); if (!t) return statusBadge(false, "", "—"); const s = el("span", `status ${t}`); s.append(icon(t === "good" ? "check" : t === "warn" ? "alert" : "stop"), document.createTextNode(text)); return s; };
    let longest = 0, run = 0, prevT = null;
    rows.forEach((r) => {
      const closed = r.flags != null && (r.flags & 1);
      run = closed ? run + (prevT == null ? src.step : Math.min(r.t - prevT, src.gap)) : 0;
      longest = Math.max(longest, run); prevT = r.t;
    });
    const yawns = rows.length ? rows[rows.length - 1]._yawns - rows[0]._yawns : 0;
    const kv = el("div", "kv");
    kvRow(kv, "eyeOff", "PERCLOS now", badge(now && now.perclos_pct, now ? `${fmt(now.perclos_pct, 0)} %` : "—"), `drowsy ≥ ${PERCLOS_DROWSY} %`);
    kvRow(kv, "eyeOff", "PERCLOS peak", badge(peak, peak == null ? "—" : `${fmt(peak, 0)} %`));
    kvRow(kv, "blink", "Blinks per minute", br.length ? fmt(br[br.length - 1], 0) : "—", br.length ? `avg ${fmt(br.reduce((a, v) => a + v, 0) / br.length, 0)}` : "");
    kvRow(kv, "mouth", "Yawns", String(Math.max(0, yawns)), src.label);
    kvRow(kv, "timer", "Longest eye closure", longest ? `${fmt(longest, 1)} s` : "—");
    b.append(kv);
    b.append(el("p", "fine", "PERCLOS is the standard drowsiness measure: the share of time the eyes are closed. Alert drivers stay well under 15 %."));
  }
  return { render, showT() {}, clearT() {} };
}

/* ================================================================ cabin air */
const AIR_CFG = { title: "Cabin air", sub: "relative to clean air, from the Arduino sensors", unit: "×", digits: 2,
  includeZero: true, minSpan: 1, floor: 0, emptyText: "No cabin air data: the Arduino isn't connected, or its sensors are still warming up",
  series: [{ key: "mq3_rel", label: "Alcohol (MQ-3)", short: "MQ-3", token: "--series-1" }, { key: "mq2_rel", label: "Smoke, gas (MQ-2)", short: "MQ-2", token: "--series-2" }],
  ref: { key: "air_ref", label: "clean air", unit: "×" } };
const withAir = (source) => () => {
  const src = source();
  return { ...src, rows: src.rows.map((r) => (r.mq3_rel != null || r.mq2_rel != null ? { ...r, air_ref: 1 } : r)) };
};

/* ================================================================ detector lanes */
const LANES = [
  { bit: 1, label: "Eyes closed", group: "drowsy" }, { bit: 2, label: "Yawning", group: "drowsy" },
  { bit: 8, label: "Head lean", group: "drowsy" }, { bit: 4, label: "Looking away", group: "distract" },
  { bit: 16, label: "Phone", group: "distract" }, { bit: 32, label: "Eating / drinking", group: "distract" },
  { bit: 64, label: "Smoking", group: "distract" }, { bit: 128, label: "Seatbelt off", group: "safety" },
  { bit: 256, label: "Driver absent", group: "safety" }, { bit: 512, label: "Camera blocked", group: "safety" },
];
const LANE_GROUPS = { drowsy: { label: "Drowsiness", token: "--series-1" }, distract: { label: "Distraction", token: "--series-2" },
                      safety: { label: "Seatbelt & presence", token: "--ink-2" } };
/* One row per detector, shaded wherever it fired - shows WHY risk rose. */
function lanesChart(card, source, opts = {}) {
  const shell = chartShell(card, "What the detectors saw", "each row is shaded while that detector was active",
    Object.values(LANE_GROUPS).map((g) => ({ token: g.token, label: g.label, rect: true })));
  let cur = null;
  function bands(rows, src) {
    const out = LANES.map((l) => ({ ...l, spans: [] }));
    rows.forEach((r) => {
      if (r.flags == null) return;
      out.forEach((l) => {
        if (!(r.flags & l.bit)) return;
        const last = l.spans[l.spans.length - 1];
        if (last && r.t - last.end <= src.gap) last.end = r.t + src.step;
        else l.spans.push({ start: r.t, end: r.t + src.step, ts: r.ts });
      });
    });
    return out;
  }
  function render() {
    const src = source(), { rows, t0, t1 } = src;
    const lanes = bands(rows, src), shown = lanes.filter((l) => l.spans.some((sp) => sp.end >= t0 && sp.start <= t1));
    if (shell.showTable) {
      const all = lanes.flatMap((l) => l.spans.map((sp) => ({ l, sp }))).sort((a, b) => b.sp.ts - a.sp.ts).slice(0, 200);
      renderTable(shell.tableWrap, ["Detector", "Started", "Lasted"], all.map(({ l, sp }) => [l.label, clock(sp.ts), duration(sp.end - sp.start)]));
      return;
    }
    cur = null;
    if (!rows.length) { shell.plot.replaceChildren(el("div", "empty", "No data yet")); return; }
    if (rows.every((r) => r.flags == null)) { shell.plot.replaceChildren(el("div", "empty", "Not recorded for this session — recorded from this version on")); return; }
    if (!shown.length) { shell.plot.replaceChildren(el("div", "empty", "No detector fired in this period")); return; }
    const W = shell.plot.clientWidth || 300, labelW = W < 520 ? 100 : 128, rowH = 16, gapR = 6;
    const pad = { l: labelW, r: 14, t: 6, b: 24 }, pw = W - pad.l - pad.r, H = pad.t + shown.length * (rowH + gapR) - gapR + pad.b;
    const x = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * pw;
    const svg = svgEl("svg", { class: "plot", viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "data-w": W,
      "aria-label": `Detectors active - ${src.label}: ${shown.map((l) => l.label).join(", ")}` });
    shown.forEach((l, i) => {
      const y = pad.t + i * (rowH + gapR);
      const lab = svgEl("text", { class: "lane-label", x: pad.l - 10, y: y + rowH / 2 + 4, "text-anchor": "end" }); lab.textContent = l.label; svg.append(lab);
      svg.append(svgEl("rect", { x: pad.l, y, width: pw, height: rowH, rx: 4, style: "fill:var(--surface-2)" }));
      l.spans.forEach((sp) => {
        const a = Math.max(x(sp.start), pad.l), b = Math.min(x(sp.end), pad.l + pw);
        if (b <= a) return;
        svg.append(svgEl("rect", { x: a, y, width: Math.max(2, b - a), height: rowH, rx: 3, style: `fill:var(${LANE_GROUPS[l.group].token})` }));
      });
    });
    xTicks(src, W).forEach((tk) => {
      const tx = svgEl("text", { class: "tick", x: x(tk.t), y: H - 6, "text-anchor": tk.label === "now" ? "end" : "middle" });
      tx.textContent = tk.label; svg.append(tx);
    });
    const hover = svgEl("g", {}); svg.append(hover);
    const hit = svgEl("rect", { x: pad.l, y: 0, width: pw, height: H - pad.b, fill: "transparent", tabindex: "0",
      "aria-label": "Detector lanes: use left and right arrow keys to read which detectors were active" });
    svg.append(hit);
    const nearestT = (t) => {
      let lo = 0, hi = rows.length - 1;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (rows[mid].t < t) lo = mid + 1; else hi = mid; }
      return lo;
    };
    const draw = (i) => { const cx = x(rows[i].t); hover.replaceChildren(svgEl("line", { class: "xhair", x1: cx, x2: cx, y1: 0, y2: H - pad.b })); return rows[i]; };
    cur = { hover, draw, nearestT, t0, t1 };
    attachHover(svg, card, hit, {
      hover, count: () => rows.length,
      nearest: (evt) => { const rect = svg.getBoundingClientRect(), px = (evt.clientX - rect.left) * (W / rect.width); return nearestT(t0 + ((px - pad.l) / pw) * (t1 - t0)); },
      at: (i) => {
        const r = draw(i), on = LANES.filter((l) => r.flags != null && (r.flags & l.bit));
        const tipRows = on.length ? on.map((l) => [`var(${LANE_GROUPS[l.group].token})`, l.label, ""]) : [["var(--axis)", "none", "no detector active"]];
        return { x: x(r.t), t: r.t, title: clock(r.ts), rows: tipRows };
      },
      onShow: opts.group && ((t) => opts.group.show(self, t)),
      onClear: opts.group && (() => opts.group.clear(self)),
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  const self = {
    render,
    showT(t) { if (cur && !shell.showTable && t >= cur.t0 && t <= cur.t1) cur.draw(cur.nearestT(t)); else this.clearT(); },
    clearT() { if (cur) cur.hover.replaceChildren(); },
  };
  if (opts.group) opts.group.add(self);
  return self;
}

/* ================================================================ reaction to alerts */
/* Every alert as a dot: how long until it was spoken, and how long after
   that until the driver corrected it (risk back down). Medians as ticks. */
function median(a) { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
function reactionChart(card, getEpisodes) {
  const shell = chartShell(card, "Reaction to alerts", "how fast the system warned, and how fast the driver fixed it",
    [{ token: "--series-1", label: "Alert raised until the voice warned", rect: true }, { token: "--series-2", label: "Voice until the driver corrected it", rect: true }]);
  function render() {
    const eps = (getEpisodes() || []).filter((e) => e.case);
    if (shell.showTable) {
      renderTable(shell.tableWrap, ["Time", "Alert", "Highest level", "Voice warned after", "Driver corrected after", "Lasted"],
        eps.slice().sort((a, b) => b.start - a.start).map((e) => [clock(e.start), caseName(e.case), lv(e.peak).word,
          e.voice_s == null ? "not spoken" : `${fmt(e.voice_s, 1)} s`, e.fix_s == null ? (e.open ? "still active" : "not measured") : `${fmt(e.fix_s, 1)} s`, duration(e.dur)]));
      return;
    }
    if (!eps.length) { shell.plot.replaceChildren(el("div", "empty", "No alerts in this session - or it was recorded before this was measured")); return; }
    const voice = eps.map((e) => e.voice_s).filter((v) => v != null), fix = eps.map((e) => e.fix_s).filter((v) => v != null);
    // three headline answers, in words
    const heads = el("div", "rx-heads");
    const head = (value, text) => { const d = el("div", "rx-head"); d.append(el("b", null, value), el("span", null, text)); heads.append(d); };
    head(voice.length ? `${fmt(median(voice), 1)} s` : "—", "typical time from an alert to the spoken warning");
    head(fix.length ? `${fmt(median(fix), 1)} s` : "—", "typical time for the driver to correct it after the warning");
    head(`${fix.length} of ${eps.length}`, `alert${eps.length === 1 ? "" : "s"} corrected by the driver`);
    // one bar per alert type: [until the voice][until corrected], medians
    const byCase = {};
    eps.forEach((e) => { (byCase[e.case] = byCase[e.case] || []).push(e); });
    const rows = Object.entries(byCase).map(([c, list]) => {
      const v = median(list.map((e) => e.voice_s).filter((x) => x != null)), f = median(list.map((e) => e.fix_s).filter((x) => x != null));
      return { c, list, v, f, total: (v || 0) + (f || 0), fixed: list.filter((e) => e.fix_s != null).length };
    }).sort((a, b) => b.list.length - a.list.length || b.total - a.total);
    const scale = niceTicks(0, Math.max(1, ...rows.map((r) => r.total)), 4), pct = (x) => `${(x / scale.hi) * 100}%`;
    const list = el("div", "rx-rows");
    rows.forEach((r) => {
      const row = el("div", "rx-row"); row.tabIndex = 0;
      const name = el("div", "rx-name"); name.append(el("b", null, caseName(r.c)), el("span", null, `${r.list.length} alert${r.list.length === 1 ? "" : "s"}`));
      const track = el("div", "rx-track");
      if (r.v != null) { const sv = el("i", "rx-v"); sv.style.width = pct(Math.max(r.v, scale.hi * 0.006)); track.append(sv); }
      if (r.f != null) { const sf = el("i", "rx-f"); sf.style.width = pct(r.f); track.append(sf); }
      const words = r.v == null ? "never spoken (voice off or muted)"
        : `warned after ${fmt(r.v, 1)} s` + (r.f != null ? `, corrected ${fmt(r.f, 1)} s later` : ", not corrected while it lasted");
      const say = el("div", "rx-say", words);
      if (r.fixed < r.list.length && r.f != null) say.append(el("small", null, ` (${r.list.length - r.fixed} not corrected)`));
      row.append(name, track, say);
      row.setAttribute("aria-label", `${caseName(r.c)}: ${r.list.length} alerts, ${words}`);
      const tip = () => [["var(--series-1)", r.v == null ? "—" : `${fmt(r.v, 1)} s`, "until the voice warned (median)"],
        ["var(--series-2)", r.f == null ? "—" : `${fmt(r.f, 1)} s`, "until corrected (median)"],
        ["var(--axis)", `${r.fixed} of ${r.list.length}`, "corrected"]];
      const show = (e) => { const cr = card.getBoundingClientRect(), tr = track.getBoundingClientRect();
        showTip(card, (e && e.clientX ? e.clientX : tr.left + tr.width / 2) - cr.left, tr.top - cr.top + 6, caseName(r.c), tip()); };
      row.addEventListener("pointermove", show); row.addEventListener("pointerleave", hideTip);
      row.addEventListener("focus", () => show()); row.addEventListener("blur", hideTip);
      list.append(row);
    });
    // the seconds scale sits on the same grid as the bars, under the bar column
    const axis = el("div", "rx-row rx-axis-row"), scaleEl = el("div", "rx-axis");
    scale.ticks.forEach((t) => { const k = el("span", null, `${t} s`); k.style.left = pct(t); scaleEl.append(k); });
    axis.append(el("div"), scaleEl, el("div"));
    axis.setAttribute("aria-hidden", "true");
    const foot = el("p", "fine", "Bars show the typical (median) case for each alert. Use Table to see every single alert.");
    shell.plot.replaceChildren(heads, list, axis, foot);
  }
  shell.onToggle = render;
  return { render, showT() {}, clearT() {} };
}

/* ---------------- live data source */
let liveSamples = [], lastT = -1, rangeSec = Number(store.get("dg-range", "300"));
let liveEvents = [], lastEventId = 0, liveFilter = store.get("dg-evfilter", "important"), eventsPrimed = false;
function liveSource() {
  if (!liveSamples.length) return { rows: [], t0: 0, t1: 0, gap: 1.5, step: 0.25, label: "live" };
  const t1 = liveSamples[liveSamples.length - 1].t, t0 = t1 - rangeSec;
  let lo = 0, hi = liveSamples.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (liveSamples[mid].t < t0) lo = mid + 1; else hi = mid; }
  const last = liveSamples[liveSamples.length - 1];
  const markers = liveEvents.filter((e) => e.kind === "marker").map((e) => ({ t: last.t - (last.ts - e.ts), title: e.title }));
  return { rows: liveSamples.slice(lo), t0, t1, gap: 1.5, step: 0.25, clockAxis: false, markers, label: `last ${rangeSec / 60} min` };
}
const liveGroup = syncGroup();
const livePick = (ts0, ts1) => jumpToEvents($("events"), liveFilters, ts0, ts1);   // wall-clock times
const liveFatigue = withFatigue(liveSource, () => liveSamples);
const liveCharts = [
  riskChart($("c-risk"), liveSource, { group: liveGroup, onPick: livePick }),
  lanesChart($("c-lanes"), liveSource, { group: liveGroup }),
  lineChart($("c-ear"), EAR_CFG, liveSource, { group: liveGroup }),
  lineChart($("c-mar"), MAR_CFG, liveSource, { group: liveGroup }),
  lineChart($("c-head"), HEAD_CFG, liveSource, { group: liveGroup }),
  lineChart($("c-perclos"), PERCLOS_CFG, liveFatigue, { group: liveGroup }),
  lineChart($("c-blinks"), BLINK_CFG, liveFatigue, { group: liveGroup }),
  fatigueCard($("c-fatigue"), liveFatigue),
  lineChart($("c-air"), AIR_CFG, withAir(liveSource), { group: liveGroup }),
];
document.querySelectorAll("#range button").forEach((b) => {
  b.setAttribute("aria-pressed", String(Number(b.dataset.sec) === rangeSec));
  b.onclick = () => {
    rangeSec = Number(b.dataset.sec); store.set("dg-range", String(rangeSec));
    document.querySelectorAll("#range button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    liveCharts.forEach((c) => c.render());
  };
});
async function pollHistory() {
  try {
    const h = await getJSON(`/api/history?since=${lastT}`);
    if (h.samples.length) {
      if (lastT > 0 && h.samples[0].t < lastT) liveSamples = [];   // app restarted
      liveSamples.push(...h.samples);
      lastT = liveSamples[liveSamples.length - 1].t;
      const cutoff = lastT - (h.window_sec || 600);
      let i = 0;
      while (i < liveSamples.length && liveSamples[i].t < cutoff) i++;
      if (i) liveSamples = liveSamples.slice(i);
    }
    if (view === "live") liveCharts.forEach((c) => c.render());
  } catch (e) { /* keep last render */ }
}

/* ================================================================ event lists */
const EV_ICON = { good: "check", warning: "alert", serious: "alert", critical: "stop" };
const KIND_ICON = { voice: "voice", system: "cpu", detect: "camera", risk: "info", marker: "flag", test: "flask" };
const IMPORTANT = (e) => ["marker", "voice", "test"].includes(e.kind) || ["warning", "serious", "critical"].includes(e.level);
const EV_FILTERS = [["important", "Important"], ["all", "All"], ["risk", "Risk"], ["marker", "Markers"], ["voice", "Voice"],
  ["detect", "Detection"], ["test", "Tests"], ["system", "System"]];
function renderEventList(list, events, filter, countEl, newIds) {
  const shown = events.filter((e) => filter === "all" || (filter === "important" ? IMPORTANT(e) : e.kind === filter))
    .slice().sort((a, b) => b.ts - a.ts || b.id - a.id);
  if (countEl) countEl.textContent = filter === "all" ? `${shown.length} event${shown.length === 1 ? "" : "s"}` : `${shown.length} of ${events.length}`;
  if (!shown.length) {
    const e = el("div", "empty empty-ev"); e.append(icon(events.length ? "info" : "check"),
      el("div", null, events.length ? "Nothing important so far" : "Nothing logged yet"),
      el("small", null, events.length ? `${events.length} other event${events.length === 1 ? "" : "s"} under “All”` : "Alerts, markers and tests will appear here"));
    list.replaceChildren(e); return;
  }
  list.replaceChildren(...shown.slice(0, 400).map((e) => {
    const row = el("div", `event ${e.kind === "marker" ? "marker" : e.level}${newIds && newIds.has(e.id) ? " new" : ""}`);
    row.dataset.ts = String(e.ts);
    const t = el("time", null, clock(e.ts));
    t.setAttribute("datetime", new Date(e.ts * 1000).toISOString());
    const ic = el("div", "ei"); ic.append(icon(e.kind === "marker" ? "flag" : EV_ICON[e.level] || KIND_ICON[e.kind] || "info"));
    const body = el("div"); body.append(el("div", "et", e.title));
    if (e.detail) body.append(el("div", "ed", e.detail));
    row.append(t, ic, body);
    return row;
  }));
}
/* Event filters: Important / All, plus one type at a time. */
const TYPE_FILTERS = EV_FILTERS.slice(2);
function filterBar(container, initial, onChange) {
  container.replaceChildren();
  container.setAttribute("role", "group"); container.setAttribute("aria-label", "Filter events");
  const seg = el("div", "seg seg-sm"), bImp = el("button", null, "Important"), bAll = el("button", null, "All");
  bImp.title = "Warnings, alerts, markers, spoken alerts and tests";
  seg.append(bImp, bAll);
  const sel = el("select", "type-select");
  sel.setAttribute("aria-label", "Show one type of event");
  sel.append(new Option("By type…", ""));
  TYPE_FILTERS.forEach(([k, label]) => sel.append(new Option(label, k)));
  container.append(seg, sel);
  let cur = initial;
  const set = (k, fire = true) => {
    cur = k;
    bImp.setAttribute("aria-pressed", String(k === "important"));
    bAll.setAttribute("aria-pressed", String(k === "all"));
    sel.value = TYPE_FILTERS.some(([x]) => x === k) ? k : "";
    sel.classList.toggle("on", !!sel.value);
    if (fire) onChange(k);
  };
  bImp.onclick = () => set("important"); bAll.onclick = () => set("all");
  sel.onchange = () => set(sel.value || "important");
  set(initial, false);
  return { set, get: () => cur };
}
const liveFilters = filterBar($("ev-filters"), liveFilter, (k) => { liveFilter = k; store.set("dg-evfilter", k); renderEventList($("events"), liveEvents, liveFilter, $("ev-count")); });
/* Click on the risk timeline: show the events of that stretch of time. */
function jumpToEvents(list, filters, t0, t1) {
  const pick = () => [...list.querySelectorAll(".event")].filter((r) => { const ts = Number(r.dataset.ts); return ts >= t0 - 1 && ts <= t1 + 1; });
  let rows = pick();
  if (!rows.length && filters && filters.get() !== "all") { filters.set("all"); rows = pick(); }
  if (!rows.length) { toast("No events logged in that stretch"); return; }
  list.querySelectorAll(".event.hl").forEach((r) => r.classList.remove("hl"));
  rows.forEach((r) => r.classList.add("hl"));
  const target = rows[rows.length - 1];               // the list is newest-first: the stretch's first event
  list.scrollTop += target.getBoundingClientRect().top - list.getBoundingClientRect().top - 8;
  const card = list.closest(".card"), r = card.getBoundingClientRect();
  if (r.top < 70 || r.bottom > window.innerHeight) card.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
  setTimeout(() => rows.forEach((x) => x.classList.remove("hl")), 4000);
}

async function pollEvents() {
  try {
    const r = await getJSON(`/api/events?since=${lastEventId}`);
    if (r.events.length) {
      if (lastEventId && r.events[0].id < lastEventId) liveEvents = [];
      liveEvents.push(...r.events);
      lastEventId = liveEvents[liveEvents.length - 1].id;
      if (liveEvents.length > 500) liveEvents = liveEvents.slice(-500);
      if (eventsPrimed) {        // only alarm on events that happen while watching
        r.events.forEach((e) => {
          if (e.kind === "risk" && e.level === "critical") beep(3, 1046);
          else if (e.kind === "risk" && e.level === "serious") beep(1, 784);
          if (e.kind === "test" && e.title === "Test not started") toast(`Test not started: ${e.detail}`, true);
        });
      }
      renderEventList($("events"), liveEvents, liveFilter, $("ev-count"), eventsPrimed ? new Set(r.events.map((e) => e.id)) : null);
    }
    eventsPrimed = true;
  } catch (e) { /* keep */ }
}

/* ================================================================ history */
let sessions = [], selectedId = null;
async function loadHistory() {
  try {
    const r = await getJSON("/api/sessions");
    sessions = r.sessions;
    $("hist-keep").textContent = `newest ${r.keep} kept`;
    renderHistoryList();
    if (!selectedId && sessions.length) openSession(sessions[0].id);
    else if (selectedId && !sessions.some((s) => s.id === selectedId)) { selectedId = null; $("hist-detail").replaceChildren(emptyDetail()); }
  } catch (e) {
    $("hist-list").replaceChildren(el("div", "empty", "Session history is unavailable"));
  }
}
function emptyDetail() {
  const c = el("div", "card empty-detail"); c.append(el("div", "empty", "Select a session to see its timeline, events and summary.")); return c;
}
function sessionDuration(s) {
  const end = s.ended_ts || s.last_ts || s.started_ts;
  return end - s.started_ts;
}
function alertTotal(sum) { return Object.values((sum && sum.alerts) || {}).reduce((a, b) => a + b, 0); }
$("hist-q").addEventListener("input", () => renderHistoryList());
function renderHistoryList() {
  const list = $("hist-list"), q = $("hist-q").value.trim().toLowerCase();
  if (!sessions.length) { list.replaceChildren(el("div", "empty", "No saved sessions yet")); return; }
  const shown = q ? sessions.filter((s) => `${s.label || ""} ${s.notes || ""} ${dateLabel(s.started_ts)}`.toLowerCase().includes(q)) : sessions;
  if (!shown.length) { list.replaceChildren(el("div", "empty", "No session matches")); return; }
  const firstRender = !list.classList.contains("settled");
  setTimeout(() => list.classList.add("settled"), firstRender ? 600 : 0);
  list.replaceChildren(...shown.map((s) => {
    const b = el("button", "hist-item");
    b.style.setProperty("--i", String(Math.min(shown.indexOf(s), 12)));
    b.setAttribute("role", "option");
    b.setAttribute("aria-selected", String(s.id === selectedId));
    const t1 = el("div", "t1");
    t1.append(el("span", null, s.label || `Session ${s.id}`), el("span", `tag ${s.status}`, s.status === "live" ? "Live" : s.status === "interrupted" ? "Interrupted" : "Saved"));
    const n = alertTotal(s.summary);
    b.append(t1, el("div", "t2", `${dateLabel(s.started_ts)}, ${duration(sessionDuration(s))}, ${n} alert${n === 1 ? "" : "s"}${s.markers ? `, ${s.markers} marker${s.markers === 1 ? "" : "s"}` : ""}`),
      riskStack(s.summary && s.summary.time_in, false));
    b.onclick = () => openSession(s.id);
    return b;
  }));
}
async function openSession(id) {
  selectedId = id;
  renderHistoryList();
  let s;
  try { s = await getJSON(`/api/sessions/${id}`); }
  catch (e) { toast("Could not load the session", true); return; }
  if (selectedId !== id) return;
  const detail = $("hist-detail");
  detail.replaceChildren();
  const sum = s.summary || {};

  // header
  const head = el("div", "card");
  const top = el("div", "detail-head");
  const titles = el("div", "titles");
  const title = el("input", "title");
  title.value = s.label || `Session ${s.id}`;
  title.setAttribute("aria-label", "Session name");
  title.maxLength = 120;
  title.addEventListener("keydown", (e) => { if (e.key === "Enter") title.blur(); });
  title.addEventListener("blur", async () => {
    const v = title.value.trim();
    if (!v || v === s.label) { title.value = s.label; return; }
    try { await api("POST", `/api/sessions/${s.id}`, { label: v }); s.label = v; toast("Session renamed"); loadHistory(); }
    catch (e) { toast(`Rename failed: ${e.message}`, true); }
  });
  const when = el("div", "when");
  when.append(el("span", `tag ${s.status}`, s.status === "live" ? "Live" : s.status === "interrupted" ? "Interrupted" : "Saved"),
    el("span", null, `${new Date(s.started_ts * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}, ${duration(sessionDuration(s))}`
      + (() => { const n = s.events.filter((e) => e.kind === "marker").length; return n ? `, ${n} marker${n === 1 ? "" : "s"}` : ""; })()));
  titles.append(title, when);
  const acts = el("div", "acts");
  const exp1 = el("a", "btn"); exp1.href = `/api/sessions/${s.id}/samples.csv`; exp1.append(icon("download"), el("span", null, "Timeline CSV"));
  const exp2 = el("a", "btn"); exp2.href = `/api/sessions/${s.id}/events.csv`; exp2.append(icon("download"), el("span", null, "Events CSV"));
  const del = el("button", "danger"); del.append(icon("trash"), el("span", null, "Delete"));
  del.disabled = s.status === "live";
  del.title = s.status === "live" ? "This session is still running" : "Delete this session";
  del.onclick = async () => {
    if (!(await dialog({ title: "Delete this session?", body: `“${s.label}” and its events and timeline will be removed permanently.`, confirm: "Delete", danger: true }))) return;
    try { await api("DELETE", `/api/sessions/${s.id}`); toast("Session deleted"); selectedId = null; detail.replaceChildren(emptyDetail()); loadHistory(); }
    catch (e) { toast(`Delete failed: ${e.message}`, true); }
  };
  const rep_ = el("a", "btn"); rep_.href = `#report/${s.id}`; rep_.append(icon("report"), el("span", null, "Report"));
  rep_.title = "A printable report of this session (Print / Save as PDF)";
  const cmp = el("button"); cmp.append(icon("compare"), el("span", null, "Compare"));
  cmp.title = "Compare this session with another one";
  cmp.disabled = sessions.length < 2;
  cmp.onclick = async () => {
    const others = sessions.filter((x) => x.id !== s.id);
    const b = await dialog({ title: "Compare with…", confirm: "Compare", select: { label: "Other session", options: others.map((x) => [x.id, `${x.label || `Session ${x.id}`} (${dateLabel(x.started_ts)})`]), value: others[0] && others[0].id } });
    if (b) location.hash = `#compare/${s.id}/${b}`;
  };
  acts.append(rep_, cmp, exp1, exp2, del);
  top.append(titles, acts);

  // tiles
  const tiles = el("div", "tiles");
  const tile = (ic, k, v, sub) => { const t = el("div", "tile"); const kk = el("div", "k"); kk.append(icon(ic), document.createTextNode(k)); t.append(kk, el("div", "v", v)); if (sub) t.append(el("div", "s", sub)); tiles.append(t); };
  const tin = sum.time_in || {}, tot = RISK_ORDER.reduce((a, r) => a + (tin[r] || 0), 0);
  const topAlert = Object.entries(sum.alerts || {}).sort((a, b) => b[1] - a[1])[0];
  const req = sum.requirements || {};
  tile("timer", "Duration", duration(sessionDuration(s)));
  tile("alert", "Alerts", String(alertTotal(sum)), topAlert ? `most: ${caseName(topAlert[0]).toLowerCase()} (${topAlert[1]})` : "none");
  tile("stop", "Time at high risk", tot ? `${Math.round((tin.HIGH || 0) / tot * 100)}%` : "—", tin.HIGH ? duration(tin.HIGH) : "");
  tile("clock", "Longest gap", sum.gap_max_ms != null ? `${Math.round(sum.gap_max_ms)} ms` : "—",
    sum.gap_max_ms != null && req.max_gap_ms ? (sum.gap_max_ms <= req.max_gap_ms ? `meets ≤ ${Math.round(req.max_gap_ms)} ms` : `exceeds ${Math.round(req.max_gap_ms)} ms`) : "");
  tile("gauge", "Update rate", sum.avg_rate_hz != null ? `${fmt(sum.avg_rate_hz, 1)} Hz` : "—",
    sum.avg_rate_hz != null && req.min_avg_rate_hz ? (sum.avg_rate_hz >= req.min_avg_rate_hz ? `meets ≥ ${req.min_avg_rate_hz} Hz` : `below ${req.min_avg_rate_hz} Hz`) : "");
  tile("bolt", "Average FPS", sum.avg_fps != null ? fmt(sum.avg_fps, 1) : "—");

  const share = el("div", "card-b");
  share.append(el("div", "sub-h", "Time by risk level"), riskStack(tin));
  const notes = el("div", "notes");
  const ta = el("textarea"); ta.placeholder = "Notes about this session (test conditions, driver, observations)…"; ta.value = s.notes || "";
  ta.setAttribute("aria-label", "Session notes");
  ta.addEventListener("change", async () => {
    try { await api("POST", `/api/sessions/${s.id}`, { notes: ta.value }); toast("Notes saved"); }
    catch (e) { toast(`Saving notes failed: ${e.message}`, true); }
  });
  notes.append(ta);
  head.append(top, tiles, share, notes);
  detail.append(head);
  if ((sum.tests || []).length) detail.append(testsCard(sum.tests));

  // charts
  const rows = s.samples.map((r) => ({ ...r, t: r.ts }));
  const markers = s.events.filter((e) => e.kind === "marker").map((e) => ({ t: e.ts, title: e.title }));
  const src = () => ({ rows, t0: rows.length ? rows[0].t : 0, t1: rows.length ? rows[rows.length - 1].t + 1 : 1, gap: 2.5, step: 1, clockAxis: true, markers, label: "whole session" });
  const grid = el("div", "detail-charts");
  const cRisk = el("div", "card wide"), cLanes = el("div", "card wide"), cEar = el("div", "card"), cMar = el("div", "card"), cHead = el("div", "card");
  const cPerclos = el("div", "card"), cBlinks = el("div", "card"), cFatigue = el("div", "card"), cReact = el("div", "card wide"), cAir = el("div", "card wide");
  grid.append(cRisk, cLanes, cReact, cEar, cMar, cHead, cPerclos, cBlinks, cFatigue, cAir);
  detail.append(grid);
  const group = syncGroup(), fsrc = withFatigue(src);
  const list = el("div", "events"), filters = el("div", "filters");
  let filterApi = null;
  const charts = [riskChart(cRisk, src, { group, onPick: (a, b) => jumpToEvents(list, filterApi, a, b) }),
    lanesChart(cLanes, src, { group }), reactionChart(cReact, () => sum.episodes),
    lineChart(cEar, EAR_CFG, src, { group }), lineChart(cMar, MAR_CFG, src, { group }), lineChart(cHead, HEAD_CFG, src, { group }),
    lineChart(cPerclos, PERCLOS_CFG, fsrc, { group }), lineChart(cBlinks, BLINK_CFG, fsrc, { group }), fatigueCard(cFatigue, fsrc),
    lineChart(cAir, AIR_CFG, withAir(src), { group })];
  charts.forEach((c) => c.render());
  historyCharts = charts;

  // events
  const evCard = el("div", "card events-card detail-events");
  const eh = el("div", "card-h"); const count = el("span", "sub");
  eh.append(el("h2", null, "Event log"), count);
  evCard.append(eh, filters, list);
  detail.append(evCard);
  filterApi = filterBar(filters, "important", (k) => renderEventList(list, s.events, k, count));
  renderEventList(list, s.events, "important", count);
}
function testsCard(tests) {
  const c = el("div", "card"), h = el("div", "card-h");
  h.append(el("h2", null, "Tests in this session"), el("span", "sub", `${tests.length} run${tests.length === 1 ? "" : "s"}`));
  const b = el("div", "card-b tests-list");
  tests.slice().reverse().forEach((t) => {
    const d = el("details", "test-item"), sm = el("summary");
    sm.append(el("b", null, t.title), t.aborted ? statusBadge(false, "", "stopped") : verdict(t.passed));
    d.append(sm, testResultNode(t));
    b.append(d);
  });
  c.append(h, b);
  return c;
}
let historyCharts = [];

/* ================================================================ report (#report/ID) */
function sessionFigures(s) {
  const sum = s.summary || {}, tin = sum.time_in || {};
  const monitored = ["SAFE", "LOW", "MEDIUM", "HIGH"].reduce((a, r) => a + (tin[r] || 0), 0);
  const share = (r) => (monitored ? (tin[r] || 0) / monitored : null);
  const alerts = Object.entries(sum.alerts || {}).sort((a, b) => b[1] - a[1]);
  return { sum, tin, monitored, share, alerts, total: alertTotal(sum), req: sum.requirements || {},
           markers: (s.events || []).filter((e) => e.kind === "marker").length, tests: sum.tests || [] };
}
function docToolbar(backHref, backLabel, extra = []) {
  const bar = el("div", "doc-bar no-print");
  const back = el("a", "btn"); back.href = backHref; back.append(icon("back"), el("span", null, backLabel));
  bar.append(back, el("span", "spacer"), ...extra);
  return bar;
}
function docSection(title, ...nodes) {
  const sec = el("section", "doc-sec"); sec.append(el("h2", null, title), ...nodes); return sec;
}
let reportCharts = [];
async function renderReport(id) {
  const root = $("view-report");
  root.replaceChildren(el("div", "empty", "Loading the report…"));
  let s;
  try { s = await getJSON(`/api/sessions/${id}`); } catch (e) { root.replaceChildren(docToolbar("#history", "History"), el("div", "empty", "That session no longer exists.")); return; }
  if (view !== "report") return;
  const f = sessionFigures(s), { sum, req } = f;
  const printBtn = el("button", "primary"); printBtn.append(icon("print"), el("span", null, "Print / Save as PDF"));
  printBtn.onclick = () => window.print();
  const page = el("article", "doc");
  // header
  const head = el("header", "doc-head");
  const brand = el("div", "doc-brand"); brand.append(el("b", "wordmark", "Driver"), el("b", "wordmark accent", "Guardian"), el("span", null, "Session report"));
  head.append(brand, el("h1", null, s.label || `Session ${s.id}`),
    el("div", "doc-meta", `${new Date(s.started_ts * 1000).toLocaleString([], { dateStyle: "full", timeStyle: "short" })}, ${duration(sessionDuration(s))}`
      + `, ${s.status === "live" ? "still running" : s.status === "interrupted" ? "interrupted" : "complete"}. Report generated ${new Date().toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`));
  page.append(head);
  // overview paragraph
  const parts = [];
  parts.push(`The session lasted ${duration(sessionDuration(s))}, of which ${duration(f.monitored)} was actively monitored.`);
  if (f.monitored) parts.push(`The driver was at high risk for ${Math.round((f.share("HIGH") || 0) * 100)} % of monitored time and at medium risk for ${Math.round((f.share("MEDIUM") || 0) * 100)} %.`);
  parts.push(f.total ? `${f.total} alert${f.total === 1 ? " was" : "s were"} raised${f.alerts[0] ? `, most often for ${caseName(f.alerts[0][0]).toLowerCase()} (${f.alerts[0][1]})` : ""}.` : "No alerts were raised.");
  if (sum.avg_rate_hz != null) parts.push(`Risk was re-classified ${fmt(sum.avg_rate_hz, 1)} times per second on average (requirement ≥ ${req.min_avg_rate_hz} Hz)${sum.gap_max_ms != null ? `, with a longest gap of ${Math.round(sum.gap_max_ms)} ms (requirement ≤ ${Math.round(req.max_gap_ms)} ms)` : ""}.`);
  const eps = (sum.episodes || []).filter((e) => e.fix_s != null);
  if (eps.length) parts.push(`After a spoken alert the driver corrected the problem in ${fmt(median(eps.map((e) => e.fix_s)), 1)} s (median of ${eps.length}).`);
  const pk = Math.max(-1, ...s.samples.map((r) => (r.perclos == null ? -1 : r.perclos * 100)));
  if (pk >= 0) parts.push(`Peak PERCLOS was ${fmt(pk, 0)} % (drowsy at ${PERCLOS_DROWSY} % and above).`);
  if (f.tests.length) parts.push(`${f.tests.length} test${f.tests.length === 1 ? " was" : "s were"} run: ${f.tests.filter((t) => t.passed).length} passed.`);
  page.append(docSection("Overview", el("p", "doc-lead", parts.join(" "))));
  // key figures
  const tiles = el("div", "tiles doc-tiles");
  const tile = (ic, k, v, sub) => { const t = el("div", "tile"); const kk = el("div", "k"); kk.append(icon(ic), document.createTextNode(k)); t.append(kk, el("div", "v", v)); if (sub) t.append(el("div", "s", sub)); tiles.append(t); };
  tile("timer", "Duration", duration(sessionDuration(s)), `${duration(f.monitored)} monitored`);
  tile("alert", "Alerts", String(f.total), f.alerts[0] ? `most: ${caseName(f.alerts[0][0]).toLowerCase()}` : "none");
  tile("stop", "Time at high risk", f.monitored ? `${Math.round((f.share("HIGH") || 0) * 100)} %` : "—", f.tin.HIGH ? duration(f.tin.HIGH) : "");
  tile("gauge", "Update rate", sum.avg_rate_hz != null ? `${fmt(sum.avg_rate_hz, 1)} Hz` : "—", `requirement ≥ ${req.min_avg_rate_hz ?? "—"} Hz`);
  tile("clock", "Longest gap", sum.gap_max_ms != null ? `${Math.round(sum.gap_max_ms)} ms` : "—", `requirement ≤ ${req.max_gap_ms ? Math.round(req.max_gap_ms) : "—"} ms`);
  tile("bolt", "Average FPS", sum.avg_fps != null ? fmt(sum.avg_fps, 1) : "—");
  const stackBox = el("div", "doc-stack"); stackBox.append(el("div", "sub-h", "Time by risk level"), riskStack(f.tin));
  page.append(docSection("Key figures", tiles, stackBox));
  // requirements
  const rq = el("table", "data doc-table"), rqb = el("tbody");
  rq.append((() => { const h = el("thead"), tr = el("tr"); ["Requirement", "Measured", "Result"].forEach((x) => tr.append(el("th", null, x))); h.append(tr); return h; })(), rqb);
  const rqRow = (name, measured, ok) => { const tr = el("tr"); const td = el("td"); td.append(ok == null ? statusBadge(false, "", "not measured") : verdict(ok)); tr.append(el("td", null, name), el("td", null, measured), td); rqb.append(tr); };
  rqRow(`Average risk update rate ≥ ${req.min_avg_rate_hz ?? "—"} Hz`, sum.avg_rate_hz != null ? `${fmt(sum.avg_rate_hz, 1)} Hz` : "—", sum.avg_rate_hz != null && req.min_avg_rate_hz ? sum.avg_rate_hz >= req.min_avg_rate_hz : null);
  rqRow(`Longest gap between updates ≤ ${req.max_gap_ms ? Math.round(req.max_gap_ms) : "—"} ms`, sum.gap_max_ms != null ? `${Math.round(sum.gap_max_ms)} ms` : "—", sum.gap_max_ms != null && req.max_gap_ms ? sum.gap_max_ms <= req.max_gap_ms : null);
  const lastOf = (pred) => f.tests.filter((t) => !t.aborted && pred(t)).pop();
  const ft = lastOf((t) => t.test === "face");
  rqRow("Eye-state accuracy ≥ 90 % (balanced)", ft ? pct1(ft.eye.balanced) : "—", ft ? ft.eye.pass : null);
  rqRow("Yawn detection accuracy ≥ 90 %", ft ? pct1(ft.yawn.accuracy) : "—", ft ? ft.yawn.pass : null);
  const dt = lastOf((t) => t.test === "delay");
  rqRow("Object detection delay ≤ 1 s (longest)", dt && dt.max != null ? `${fmt(dt.max, 2)} s (${dt.object})` : "—", dt && dt.max != null ? dt.pass : null);
  page.append(docSection("Requirements", rq));
  // charts
  const rows = s.samples.map((r) => ({ ...r, t: r.ts }));
  const markers = s.events.filter((e) => e.kind === "marker").map((e) => ({ t: e.ts, title: e.title }));
  const src = () => ({ rows, t0: rows.length ? rows[0].t : 0, t1: rows.length ? rows[rows.length - 1].t + 1 : 1, gap: 2.5, step: 1, clockAxis: true, markers, label: "whole session" });
  const grid = el("div", "detail-charts doc-charts");
  const cRisk = el("div", "card wide"), cLanes = el("div", "card wide"), cEar = el("div", "card"), cMar = el("div", "card"), cHead = el("div", "card");
  grid.append(cRisk, cLanes, cEar, cMar, cHead);
  page.append(docSection("Timeline", grid));
  const fgrid = el("div", "detail-charts doc-charts");
  const cPerclos = el("div", "card"), cBlinks = el("div", "card"), cFatigue = el("div", "card");
  fgrid.append(cPerclos, cBlinks, cFatigue);
  page.append(docSection("Fatigue", fgrid));
  const hasAir = s.samples.some((r) => r.mq3 != null || r.mq2 != null), cAir = el("div", "card");
  if (hasAir) page.append(docSection("Cabin air", cAir));
  const cReact = el("div", "card");
  page.append(docSection("Reaction to alerts", cReact));
  // alerts by type
  if (f.alerts.length) {
    const t = el("div", "table-wrap doc-free");
    renderTable(t, ["Alert", "Times raised"], f.alerts.map(([c, n]) => [caseName(c), String(n)]));
    page.append(docSection("Alerts by type", t));
  }
  if (f.tests.length) {
    const box = el("div", "doc-tests");
    f.tests.forEach((t) => { const d = el("div", "doc-test"); const h = el("h3"); h.append(document.createTextNode(t.title + " "), t.aborted ? statusBadge(false, "", "stopped") : verdict(t.passed)); d.append(h, testResultNode(t)); box.append(d); });
    page.append(docSection("Tests", box));
  }
  // events
  const imp = s.events.filter(IMPORTANT).sort((a, b) => a.ts - b.ts);
  const et = el("div", "table-wrap doc-free");
  renderTable(et, ["Time", "Event", "Detail"], imp.slice(0, 300).map((e) => [clock(e.ts), e.title, e.detail || ""]));
  et.querySelectorAll("td:first-child").forEach((td) => td.classList.add("nowrap"));
  page.append(docSection(`Important events (${imp.length}${imp.length > 300 ? ", first 300 shown" : ""})`, imp.length ? et : el("p", null, "None.")));
  if (s.notes) page.append(docSection("Notes", el("p", "doc-notes", s.notes)));
  page.append(el("footer", "doc-foot", `DriverGuardian session ${s.id}. All times are local (${Intl.DateTimeFormat().resolvedOptions().timeZone || "device time"})`));
  root.replaceChildren(docToolbar("#history", "History", [printBtn]), page);
  const group = syncGroup();
  const fsrc = withFatigue(src);
  reportCharts = [riskChart(cRisk, src, { group }), lanesChart(cLanes, src, { group }),
    lineChart(cEar, EAR_CFG, src, { group }), lineChart(cMar, MAR_CFG, src, { group }), lineChart(cHead, HEAD_CFG, src, { group }),
    lineChart(cPerclos, PERCLOS_CFG, fsrc, { group }), lineChart(cBlinks, BLINK_CFG, fsrc, { group }), fatigueCard(cFatigue, fsrc),
    reactionChart(cReact, () => sum.episodes), ...(hasAir ? [lineChart(cAir, AIR_CFG, withAir(src), { group })] : [])];
  reportCharts.forEach((c) => c.render());
  document.title = `${s.label || `Session ${s.id}`} — DriverGuardian report`;
}
window.addEventListener("beforeprint", () => reportCharts.forEach((c) => c.render()));
window.addEventListener("afterprint", () => reportCharts.forEach((c) => c.render()));

/* ================================================================ compare (#compare/A/B) */
const medFix = (s) => median(((s.summary || {}).episodes || []).map((e) => e.fix_s).filter((v) => v != null));
const peakPerclos = (s) => { const v = (s.samples || []).map((r) => r.perclos).filter((x) => x != null); return v.length ? Math.max(...v) * 100 : null; };
let compareCharts = [];
async function renderCompare(a, b) {
  const root = $("view-compare");
  root.replaceChildren(el("div", "empty", "Loading…"));
  let A, B;
  try { [A, B] = await Promise.all([getJSON(`/api/sessions/${a}`), getJSON(`/api/sessions/${b}`)]); }
  catch (e) { root.replaceChildren(docToolbar("#history", "History"), el("div", "empty", "One of these sessions no longer exists.")); return; }
  if (view !== "compare") return;
  if (!sessions.length) { try { sessions = (await getJSON("/api/sessions")).sessions; } catch (e) { /* the selector just stays short */ } }
  const fa = sessionFigures(A), fb = sessionFigures(B);
  const name = (s) => s.label || `Session ${s.id}`;
  const swap = el("a", "btn"); swap.href = `#compare/${b}/${a}`; swap.append(icon("compare"), el("span", null, "Swap"));
  const page = el("article", "doc compare");
  const head = el("header", "cmp-head");
  [[A, "--series-1", "A"], [B, "--series-2", "B"]].forEach(([s, token, letter]) => {
    const c = el("div", "cmp-who"), key = el("span", "rect-key"); key.style.background = `var(${token})`;
    const t = el("div", "t"); t.append(key, el("b", null, `${letter}: ${name(s)}`));
    c.append(t, el("div", "doc-meta", `${dateLabel(s.started_ts)}, ${duration(sessionDuration(s))}`));
    head.append(c);
  });
  page.append(el("h1", null, "Session comparison"), head);
  // metrics
  const pctOf = (f, r) => (f.monitored ? Math.round((f.share(r) || 0) * 100) : null);
  const metrics = [
    ["Duration", sessionDuration(A), sessionDuration(B), duration, null],
    ["Monitored time", fa.monitored, fb.monitored, duration, null],
    ["Alerts", fa.total, fb.total, String, "lower"],
    ["Alerts per 10 min monitored", fa.monitored ? fa.total / fa.monitored * 600 : null, fb.monitored ? fb.total / fb.monitored * 600 : null, (v) => fmt(v, 1), "lower"],
    ["Time at high risk", pctOf(fa, "HIGH"), pctOf(fb, "HIGH"), (v) => `${v} %`, "lower"],
    ["Time at medium risk", pctOf(fa, "MEDIUM"), pctOf(fb, "MEDIUM"), (v) => `${v} %`, "lower"],
    ["Time at low risk", pctOf(fa, "LOW"), pctOf(fb, "LOW"), (v) => `${v} %`, "lower"],
    ["Time safe", pctOf(fa, "SAFE"), pctOf(fb, "SAFE"), (v) => `${v} %`, "higher"],
    ["Update rate", fa.sum.avg_rate_hz, fb.sum.avg_rate_hz, (v) => `${fmt(v, 1)} Hz`, "higher"],
    ["Longest update gap", fa.sum.gap_max_ms, fb.sum.gap_max_ms, (v) => `${Math.round(v)} ms`, "lower"],
    ["Average FPS", fa.sum.avg_fps, fb.sum.avg_fps, (v) => fmt(v, 1), "higher"],
    ["Median time to correct after the voice", medFix(A), medFix(B), (v) => `${fmt(v, 1)} s`, "lower"],
    ["Peak PERCLOS", peakPerclos(A), peakPerclos(B), (v) => `${fmt(v, 0)} %`, "lower"],
    ["Markers", fa.markers, fb.markers, String, null],
    ["Tests passed", fa.tests.length ? fa.tests.filter((t) => t.passed).length : null, fb.tests.length ? fb.tests.filter((t) => t.passed).length : null, String, null],
  ];
  const tbl = el("table", "data cmp-table"), th = el("thead"), tr0 = el("tr");
  ["", "A", "B", "B compared with A"].forEach((x) => tr0.append(el("th", null, x))); th.append(tr0);
  const tb = el("tbody");
  metrics.forEach(([label, va, vb, f, better]) => {
    const tr = el("tr"), diff = el("td", "diff");
    if (va != null && vb != null && typeof va === "number" && va !== vb) {
      const up = vb > va, good = better ? (better === "higher") === up : null;
      const d = el("span", good == null ? "neutral" : good ? "better" : "worse");
      d.append(document.createTextNode(`${up ? "▲" : "▼"} ${f === duration ? duration(Math.abs(vb - va)) : f(Math.abs(vb - va))}`));
      if (good != null) d.append(el("small", null, good ? " better" : " worse"));
      diff.append(d);
    } else diff.textContent = va != null && vb != null ? "same" : "";
    tr.append(el("td", null, label), el("td", null, va == null ? "—" : f(va)), el("td", null, vb == null ? "—" : f(vb)), diff);
    tb.append(tr);
  });
  tbl.append(th, tb);
  page.append(docSection("Figures", tbl));
  // time by risk level
  const shares = el("div", "cmp-shares");
  [[A, fa, "A"], [B, fb, "B"]].forEach(([s, f, letter]) => { const row = el("div", "cmp-share"); row.append(el("b", null, letter), riskStack(f.tin, false)); shares.append(row); });
  const lg = el("div", "stack-legend cmp-legend");
  RISK_ORDER.forEach((r) => { const k = el("div", "k"), ic = icon(lv(r).icon); ic.style.color = `var(${lv(r).token})`; k.append(ic, document.createTextNode(lv(r).word)); lg.append(k); });
  page.append(docSection("Time by risk level", shares, lg));
  // alerts by type: grouped bars, A = series 1, B = series 2
  const cases = [...new Set([...fa.alerts.map((x) => x[0]), ...fb.alerts.map((x) => x[0])])];
  const am = Object.fromEntries(fa.alerts), bm = Object.fromEntries(fb.alerts);
  cases.sort((x, y) => ((bm[y] || 0) + (am[y] || 0)) - ((bm[x] || 0) + (am[x] || 0)));
  const chartCard = el("div", "card cmp-alerts");
  const ch = el("div", "card-h"); ch.append(el("h2", null, "Alerts by type"), el("span", "sub", "times each alert was raised"));
  const legend = el("div", "legend");
  [["--series-1", `A: ${name(A)}`], ["--series-2", `B: ${name(B)}`]].forEach(([tok, label]) => { const k = el("span", "k"), key = el("span", "rect-key"); key.style.background = `var(${tok})`; k.append(key, document.createTextNode(label)); legend.append(k); });
  const body = el("div", "card-b");
  if (!cases.length) body.append(el("div", "empty", "Neither session raised an alert"));
  else {
    const max = Math.max(1, ...cases.map((c) => Math.max(am[c] || 0, bm[c] || 0)));
    const gb = el("div", "gbars");
    cases.forEach((c) => {
      const row = el("div", "gb-row"); row.tabIndex = 0;
      const bars = el("div", "gb-bars");
      [[am[c] || 0, "--series-1"], [bm[c] || 0, "--series-2"]].forEach(([n, tok]) => {
        const line = el("div", "gb-line"), bar = el("i"); bar.style.width = `${(n / max) * 100}%`; bar.style.background = `var(${tok})`;
        if (!n) bar.classList.add("zero");
        line.append(bar, el("span", null, String(n))); bars.append(line);
      });
      row.append(el("div", "gb-label", caseName(c)), bars);
      const tipRows = () => [["var(--series-1)", String(am[c] || 0), `A: ${name(A)}`], ["var(--series-2)", String(bm[c] || 0), `B: ${name(B)}`]];
      row.addEventListener("pointermove", (e) => { const r = chartCard.getBoundingClientRect(); showTip(chartCard, e.clientX - r.left, e.clientY - r.top, caseName(c), tipRows()); });
      row.addEventListener("pointerleave", hideTip);
      row.addEventListener("focus", () => { const r = chartCard.getBoundingClientRect(), rr = row.getBoundingClientRect(); showTip(chartCard, rr.left - r.left + 160, rr.top - r.top + 10, caseName(c), tipRows()); });
      row.addEventListener("blur", hideTip);
      gb.append(row);
    });
    body.append(gb);
  }
  chartCard.append(ch, legend, body);
  page.append(chartCard);
  // risk timelines, one per session (each on its own clock)
  const tl = el("div", "cmp-timelines");
  compareCharts = [A, B].map((s, i) => {
    const rows = s.samples.map((r) => ({ ...r, t: r.ts }));
    const card = el("div", "card"); tl.append(card);
    const ch = riskChart(card, () => ({ rows, t0: rows.length ? rows[0].t : 0, t1: rows.length ? rows[rows.length - 1].t + 1 : 1, gap: 2.5, step: 1, clockAxis: true, markers: [], label: name(s) }));
    return { card, ch, title: `${i ? "B" : "A"}: ${name(s)}` };
  });
  page.append(docSection("Risk timelines", tl));
  // the other session can be changed in place
  const pickB = el("select", "cmp-pick"); pickB.setAttribute("aria-label", "Compare A with");
  sessions.filter((x) => x.id !== A.id).forEach((x) => { const o = el("option", null, `B: ${x.label || `Session ${x.id}`} (${dateLabel(x.started_ts)})`); o.value = String(x.id); pickB.append(o); });
  pickB.value = String(B.id);
  pickB.onchange = () => { location.hash = `#compare/${A.id}/${pickB.value}`; };
  root.replaceChildren(docToolbar("#history", "History", [pickB, swap]), page);
  compareCharts.forEach(({ card, ch, title }) => { ch.render(); const h = card.querySelector(".card-h h2"); if (h) h.textContent = title; });
  compareCharts = compareCharts.map((x) => ({ render: () => { x.ch.render(); const h = x.card.querySelector(".card-h h2"); if (h) h.textContent = x.title; } }));
}

/* ================================================================ keyboard */
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea, select, dialog") || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (e.key === "?") { showHelp(); e.preventDefault(); return; }
  if (k === "l") { if (kioskOn) setKiosk(false); setView("live"); e.preventDefault(); return; }
  if (k === "h") { if (kioskOn) setKiosk(false); setView("history"); e.preventDefault(); return; }
  if (view !== "live") return;
  if (k === "escape" && kioskOn && !document.fullscreenElement) { setKiosk(false); e.preventDefault(); }
  else if (k === "k") { setKiosk(!kioskOn); e.preventDefault(); }
  else if (k === "p") { togglePause(); e.preventDefault(); }
  else if (k === "m") { addMarker(); e.preventDefault(); }
  else if (k === "t") { openTests(); e.preventDefault(); }
  else if (k === "f") { $("btn-full").click(); e.preventDefault(); }
});

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => ({ live: liveCharts, history: historyCharts, report: reportCharts, compare: compareCharts }[view] || []).forEach((c) => c.render()), 150);
});

/* ================================================================ start */
route();
pollState(); pollHistory(); pollEvents();
setInterval(pollState, 500);
setInterval(pollHistory, 1000);
setInterval(pollEvents, 1000);
setInterval(() => { if (state) renderHero(); setConnection(); }, 1000);
setInterval(() => { if (view === "history") loadHistory(); }, 10000);
