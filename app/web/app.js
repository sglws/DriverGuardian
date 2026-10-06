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
  PAUSED: "Monitoring paused",
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
  return `${day} · ${clock(ts, false)}`;
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
let theme = store.get("dg-theme", "auto");
function applyTheme() {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  $("btn-theme").title = `Theme: ${theme === "auto" ? "follows the system" : theme}`;
}
$("btn-theme").onclick = () => { theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]; store.set("dg-theme", theme); applyTheme(); };
applyTheme();

/* ================================================================ api, toasts, dialogs */
async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}
async function api(method, url, body) {
  const r = await fetch(url, { method, headers: { "X-DriverGuardian": "1", "Content-Type": "application/json" },
                               body: body ? JSON.stringify(body) : undefined });
  let data = {};
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok) throw new Error(data.error || `request failed (${r.status})`);
  return data;
}
function toast(msg, err = false) {
  const t = el("div", `toast${err ? " err" : ""}`);
  t.append(icon(err ? "alert" : "check"), document.createTextNode(msg));
  $("toasts").append(t);
  setTimeout(() => { t.classList.add("out"); t.addEventListener("animationend", () => t.remove()); setTimeout(() => t.remove(), 400); }, 3000);
}
const dlg = $("dlg");
function dialog({ title, body = "", confirm = "OK", danger = false, input = null }) {
  $("dlg-title").textContent = title;
  $("dlg-body").textContent = body;
  $("dlg-body").hidden = !body;
  $("dlg-field").hidden = !input;
  if (input) { $("dlg-label").textContent = input.label || ""; $("dlg-input").value = input.value || ""; $("dlg-input").placeholder = input.placeholder || ""; }
  const ok = $("dlg-ok");
  ok.textContent = confirm;
  ok.className = danger ? "danger solid" : "primary";
  return new Promise((resolve) => {
    dlg.onclose = () => resolve(dlg.returnValue === "ok" ? (input ? $("dlg-input").value.trim() : true) : null);
    dlg.returnValue = "";
    dlg.showModal();
    (input ? $("dlg-input") : $("dlg-cancel")).focus();
  });
}

/* ================================================================ tabs */
let view = "live";
function setView(v) {
  view = v;
  $("tab-live").setAttribute("aria-selected", String(v === "live"));
  $("tab-history").setAttribute("aria-selected", String(v === "history"));
  $("view-live").hidden = v !== "live";
  $("view-history").hidden = v !== "history";
  if (v === "live") { startVideo(); liveCharts.forEach((c) => c.render()); } else { stopVideo(); loadHistory(); }
  if (location.hash !== `#${v}`) history.replaceState(null, "", `#${v}`);
}
$("tab-live").onclick = () => setView("live");
$("tab-history").onclick = () => setView("history");

/* ================================================================ video */
const video = $("video");
let videoOn = false;
function startVideo() { if (videoOn) return; videoOn = true; video.src = "/stream.mjpg?t=" + Date.now(); }
function stopVideo() { videoOn = false; video.removeAttribute("src"); video.classList.remove("ready"); }
video.onerror = () => { if (!videoOn) return; video.classList.remove("ready"); $("video-wait").hidden = false; videoOn = false; setTimeout(() => view === "live" && startVideo(), 2000); };
video.onload = () => { $("video-wait").hidden = true; video.classList.add("ready"); };
$("btn-full").onclick = () => {
  const box = $("video-box");
  if (document.fullscreenElement) document.exitFullscreen();
  else if (box.requestFullscreen) box.requestFullscreen();
};

/* ================================================================ browser sound */
let soundOn = store.get("dg-sound", "0") === "1";
let audioCtx = null;
function setSound(on) {
  soundOn = on; store.set("dg-sound", on ? "1" : "0");
  $("btn-sound").setAttribute("aria-pressed", String(on));
  $("btn-sound").title = on ? "Browser sound on: plays when risk turns high or medium" : "Play a sound in this browser when risk turns high";
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
  renderPanels();
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
    ? `${s.recording ? "Recording" : "Not recorded"} · started ${clock(s.started_ts, false)} · ${duration(s.uptime_s)}`
      + (state.history_keep ? ` · history keeps the last ${state.history_keep} sessions` : "")
    : "";
  const pause = $("btn-pause");
  pause.setAttribute("aria-pressed", String(!!state.paused));
  pause.replaceChildren(icon(state.paused ? "play" : "pauseBars"), el("span", null, state.paused ? "Resume" : "Pause"));
  const muted = !!(state.links && state.links.muted);
  const mute = $("btn-mute");
  mute.setAttribute("aria-pressed", String(muted));
  if (mute.dataset.muted !== String(muted)) {
    mute.dataset.muted = String(muted);
    mute.replaceChildren(icon(muted ? "mute" : "voice"));
    mute.setAttribute("aria-label", muted ? "Unmute voice alerts" : "Mute voice alerts");
    mute.title = muted ? "Voice alerts are muted - click to unmute" : "Mute the spoken alerts";
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

/* ---------------- hero */
function setAnimated(node, text) {
  if (node.textContent === text) return;
  node.textContent = text;
  node.classList.remove("changed");
  void node.offsetWidth;           // restart the animation
  node.classList.add("changed");
}
function renderHero() {
  const L = lv(state.risk);
  const key = `${state.risk}|${state.paused}|${state.calibrating}`;
  if (riskSince.key !== key) riskSince = { key, at: Date.now() };
  const hero = $("hero");
  hero.style.setProperty("--level", `var(${L.token})`);
  const iconName = state.paused ? "pause" : L.icon;
  if ($("hero-icon").dataset.icon !== iconName) { $("hero-icon").replaceChildren(icon(iconName)); $("hero-icon").dataset.icon = iconName; }
  setAnimated($("hero-level"), state.calibrating ? "Calibrating" : state.paused ? "Paused" : L.word);
  const levelWord = state.calibrating ? "Calibrating" : state.paused ? "Paused" : L.word;
  setAnimated($("hero-case"), caseName(state.case) === levelWord ? "" : caseName(state.case));
  const active = !state.paused && !state.calibrating;
  hero.classList.toggle("attn", active && state.risk === "HIGH");
  const idx = active ? ["SAFE", "LOW", "MEDIUM", "HIGH"].indexOf(state.risk) : -1;
  $("hero-ladder").querySelectorAll("div").forEach((d, i) => {
    d.classList.toggle("on", i === idx);
    d.classList.toggle("reached", idx > 0 && i < idx);
  });
  const msg = (state.messages || [])[0] || "";
  $("hero-msg").textContent = msg === caseName(state.case) ? "" : msg;
  $("hero-for").textContent = duration((Date.now() - riskSince.at) / 1000);
  $("hero-score").textContent = state.score != null ? state.score : "—";
  const rate = state.perf && state.perf.rate_hz;
  $("hero-rate").textContent = rate != null ? `${fmt(rate, 1)} Hz` : "—";
}

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
      `EAR ${fmt(e.ear)} · limit ${fmt(e.ear_thr)}`, closedLong ? "crit" : e.closed ? "warn" : "ok"]);
    rows.push(["blinks", "blink", "Blinks", `${e.blink_rate} in last ${Math.round(e.blink_window_sec)} s`, `${e.blinks_total} in session`, e.level === "DROWSY" ? "warn" : ""]);
  } else {
    rows.push(["eyes", "eye", "Eyes", "—", noFace, ""]);
    rows.push(["blinks", "blink", "Blinks", "—", "", ""]);
  }
  if (m) rows.push(["mouth", "mouth", "Mouth", m.yawning ? "Yawning" : m.open ? "Open" : "Closed", `MAR ${fmt(m.mar)} · ${m.yawns_total} yawn${m.yawns_total === 1 ? "" : "s"}`, m.yawning ? "warn" : "ok"]);
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
  const box = $("chips");
  if (box.children.length !== rows.length) box.replaceChildren(...rows.map(() => { const c = el("div", "chip"); c.append(el("div", "ci"), el("div")); return c; }));
  rows.forEach(([, ic, label, value, extra, tone], i) => {
    const c = box.children[i];
    const prev = c.dataset.tone;
    c.dataset.tone = tone || "";
    c.className = `chip ${tone || ""}`;
    if (prev !== undefined && prev !== (tone || "") && (tone === "warn" || tone === "crit")) {
      c.classList.add("flash");
      c.addEventListener("animationend", () => c.classList.remove("flash"), { once: true });
    }
    const ci = c.children[0];
    if (ci.dataset.icon !== ic) { ci.replaceChildren(icon(ic)); ci.dataset.icon = ic; }
    const body = c.children[1];
    body.replaceChildren(el("div", "ck", label), el("div", "cv", value));
    if (extra) body.append(el("div", "cx", extra));
  });
}

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
      b.append(icon(tone === "good" ? "check" : tone === "warn" ? "alert" : "stop"), document.createTextNode(`${fmt(t, 1)} °C${thr ? " · throttling" : ""}`));
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
  // opts: { count, at(i) -> {x, rows, title}, nearest(evt) -> i, hover <g> }
  let idx = null;
  const show = (i) => {
    if (!opts.count()) return;
    idx = Math.max(0, Math.min(opts.count() - 1, i));
    const r = opts.at(idx);
    const svgRect = svg.getBoundingClientRect(), cardRect = card.getBoundingClientRect(), W = +svg.getAttribute("data-w");
    showTip(card, (svgRect.left - cardRect.left) + r.x * (svgRect.width / W), (svgRect.top - cardRect.top) + 18, r.title, r.rows);
  };
  const clear = () => { idx = null; opts.hover.replaceChildren(); hideTip(); };
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

/* Line chart (one y-axis, shared unit). source() -> {rows, t0, t1, clockAxis, gap, label} */
function lineChart(card, cfg, source) {
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
    if (!rows.length || vals.length <= (cfg.includeZero ? 1 : 0)) { shell.plot.replaceChildren(el("div", "empty", "No data yet — waiting for the driver's face")); return; }
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
          lbl.textContent = `${cfg.ref.label} ${fmt(last[cfg.ref.key], cfg.digits)}`; svg.append(lbl);
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
    attachHover(svg, card, hit, {
      hover, count: () => rows.length,
      nearest: (evt) => {
        const rect = svg.getBoundingClientRect(), px = (evt.clientX - rect.left) * (W / rect.width), t = t0 + ((px - pad.l) / pw) * (t1 - t0);
        let lo = 0, hi = rows.length - 1;
        while (lo < hi) { const mid = (lo + hi) >> 1; if (rows[mid].t < t) lo = mid + 1; else hi = mid; }
        if (lo > 0 && Math.abs(rows[lo - 1].t - t) < Math.abs(rows[lo].t - t)) lo--;
        return lo;
      },
      at: (i) => {
        const r = rows[i], cx = x(r.t);
        hover.replaceChildren(svgEl("line", { class: "xhair", x1: cx, x2: cx, y1: pad.t, y2: pad.t + ph }));
        const tipRows = [];
        cfg.series.forEach((s) => {
          if (r[s.key] != null) hover.append(svgEl("circle", { class: "hover-dot", cx, cy: y(r[s.key]), r: 4, style: `fill:var(${s.token})` }));
          tipRows.push([`var(${s.token})`, r[s.key] == null ? "—" : `${fmt(r[s.key], cfg.digits)}${cfg.unit ? " " + cfg.unit : ""}`, s.label]);
        });
        if (cfg.ref && r[cfg.ref.key] != null) tipRows.push(["var(--muted)", fmt(r[cfg.ref.key], cfg.digits), cfg.ref.label]);
        return { x: cx, title: clock(r.ts), rows: tipRows };
      },
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  return { render };
}

/* Risk timeline: status-coloured segments + marker flags. */
function riskChart(card, source) {
  const shell = chartShell(card, "Risk timeline", "risk level over time · flags are markers",
    RISK_ORDER.map((r) => ({ icon: lv(r).icon, token: lv(r).token, label: lv(r).word })));
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
      "aria-label": "Risk timeline: use left and right arrow keys to step through segments" });
    svg.append(hit);
    attachHover(svg, card, hit, {
      hover, count: () => segs.length,
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
        return { x: (x(s.start) + x(s.end)) / 2, title: `${clock(s.ts)} · ${duration(s.end - s.start)}`, rows: rowsTip };
      },
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  return { render };
}

const EAR_CFG = { title: "Eye openness", sub: "eye aspect ratio (EAR)", digits: 3, minSpan: 0.1, floor: 0,
  series: [{ key: "ear", label: "EAR", token: "--series-1" }], ref: { key: "ear_thr", label: "closed below" } };
const MAR_CFG = { title: "Mouth opening", sub: "mouth aspect ratio (MAR)", digits: 3, minSpan: 0.1, floor: 0,
  series: [{ key: "mar", label: "MAR", token: "--series-1" }], ref: { key: "mar_thr", label: "open above" } };
const HEAD_CFG = { title: "Head pose", sub: "change from calibrated position", unit: "°", digits: 1, includeZero: true, minSpan: 20,
  series: [{ key: "pitch", label: "Pitch (down +)", short: "Pitch", token: "--series-1" }, { key: "yaw", label: "Yaw (right +)", short: "Yaw", token: "--series-2" }] };

/* ---------------- live data source */
let liveSamples = [], lastT = -1, rangeSec = Number(store.get("dg-range", "300"));
let liveEvents = [], lastEventId = 0, liveFilter = "all", eventsPrimed = false;
function liveSource() {
  if (!liveSamples.length) return { rows: [], t0: 0, t1: 0, gap: 1.5, step: 0.25, label: "live" };
  const t1 = liveSamples[liveSamples.length - 1].t, t0 = t1 - rangeSec;
  let lo = 0, hi = liveSamples.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (liveSamples[mid].t < t0) lo = mid + 1; else hi = mid; }
  const last = liveSamples[liveSamples.length - 1];
  const markers = liveEvents.filter((e) => e.kind === "marker").map((e) => ({ t: last.t - (last.ts - e.ts), title: e.title }));
  return { rows: liveSamples.slice(lo), t0, t1, gap: 1.5, step: 0.25, clockAxis: false, markers, label: `last ${rangeSec / 60} min` };
}
const liveCharts = [
  riskChart($("c-risk"), liveSource),
  lineChart($("c-ear"), EAR_CFG, liveSource),
  lineChart($("c-mar"), MAR_CFG, liveSource),
  lineChart($("c-head"), HEAD_CFG, liveSource),
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
const KIND_ICON = { voice: "voice", system: "cpu", detect: "camera", risk: "info", marker: "flag" };
function renderEventList(list, events, filter, countEl, newIds) {
  const shown = events.filter((e) => filter === "all" || e.kind === filter).slice().sort((a, b) => b.ts - a.ts || b.id - a.id);
  if (countEl) countEl.textContent = `${shown.length} event${shown.length === 1 ? "" : "s"}`;
  if (!shown.length) { list.replaceChildren(el("div", "empty", "Nothing logged yet")); return; }
  list.replaceChildren(...shown.slice(0, 400).map((e) => {
    const row = el("div", `event ${e.kind === "marker" ? "marker" : e.level}${newIds && newIds.has(e.id) ? " new" : ""}`);
    const t = el("time", null, clock(e.ts));
    t.setAttribute("datetime", new Date(e.ts * 1000).toISOString());
    const ic = el("div", "ei"); ic.append(icon(e.kind === "marker" ? "flag" : EV_ICON[e.level] || KIND_ICON[e.kind] || "info"));
    const body = el("div"); body.append(el("div", "et", e.title));
    if (e.detail) body.append(el("div", "ed", e.detail));
    row.append(t, ic, body);
    return row;
  }));
}
function bindFilters(container, onChange) {
  container.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      container.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      onChange(b.dataset.kind);
    };
  });
}
bindFilters($("ev-filters"), (k) => { liveFilter = k; renderEventList($("events"), liveEvents, liveFilter, $("ev-count")); });

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
function renderHistoryList() {
  const list = $("hist-list");
  if (!sessions.length) { list.replaceChildren(el("div", "empty", "No saved sessions yet")); return; }
  const firstRender = !list.classList.contains("settled");
  setTimeout(() => list.classList.add("settled"), firstRender ? 600 : 0);
  list.replaceChildren(...sessions.map((s) => {
    const b = el("button", "hist-item");
    b.style.setProperty("--i", String(Math.min(sessions.indexOf(s), 12)));
    b.setAttribute("role", "option");
    b.setAttribute("aria-selected", String(s.id === selectedId));
    const t1 = el("div", "t1");
    t1.append(el("span", null, s.label || `Session ${s.id}`), el("span", `tag ${s.status}`, s.status === "live" ? "Live" : s.status === "interrupted" ? "Interrupted" : "Saved"));
    const n = alertTotal(s.summary);
    b.append(t1, el("div", "t2", `${dateLabel(s.started_ts)} · ${duration(sessionDuration(s))} · ${n} alert${n === 1 ? "" : "s"}${s.markers ? ` · ${s.markers} marker${s.markers === 1 ? "" : "s"}` : ""}`),
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
    el("span", null, `${new Date(s.started_ts * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} · ${duration(sessionDuration(s))}`
      + (() => { const n = s.events.filter((e) => e.kind === "marker").length; return n ? ` · ${n} marker${n === 1 ? "" : "s"}` : ""; })()));
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
  acts.append(exp1, exp2, del);
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
  tile("clock", "Longest update gap", sum.gap_max_ms != null ? `${Math.round(sum.gap_max_ms)} ms` : "—",
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

  // charts
  const rows = s.samples.map((r) => ({ ...r, t: r.ts }));
  const markers = s.events.filter((e) => e.kind === "marker").map((e) => ({ t: e.ts, title: e.title }));
  const src = () => ({ rows, t0: rows.length ? rows[0].t : 0, t1: rows.length ? rows[rows.length - 1].t + 1 : 1, gap: 2.5, step: 1, clockAxis: true, markers, label: "whole session" });
  const grid = el("div", "detail-charts");
  const cRisk = el("div", "card wide"), cEar = el("div", "card"), cMar = el("div", "card"), cHead = el("div", "card");
  grid.append(cRisk, cEar, cMar, cHead);
  detail.append(grid);
  const charts = [riskChart(cRisk, src), lineChart(cEar, EAR_CFG, src), lineChart(cMar, MAR_CFG, src), lineChart(cHead, HEAD_CFG, src)];
  charts.forEach((c) => c.render());
  historyCharts = charts;

  // events
  const evCard = el("div", "card events-card detail-events");
  const eh = el("div", "card-h"); const count = el("span", "sub");
  eh.append(el("h2", null, "Event log"), count);
  const filters = el("div", "filters"); filters.setAttribute("role", "group"); filters.setAttribute("aria-label", "Filter events");
  [["all", "All"], ["risk", "Risk"], ["marker", "Markers"], ["voice", "Voice"], ["detect", "Detection"], ["system", "System"]].forEach(([k, label], i) => {
    const b = el("button", null, label); b.dataset.kind = k; b.setAttribute("aria-pressed", String(i === 0)); filters.append(b);
  });
  const list = el("div", "events");
  evCard.append(eh, filters, list);
  detail.append(evCard);
  let filter = "all";
  renderEventList(list, s.events, filter, count);
  bindFilters(filters, (k) => { filter = k; renderEventList(list, s.events, filter, count); });
}
let historyCharts = [];

/* ================================================================ keyboard */
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea, select, dialog") || e.metaKey || e.ctrlKey || e.altKey) return;
  if (view !== "live") return;
  const k = e.key.toLowerCase();
  if (k === "p") { togglePause(); e.preventDefault(); }
  else if (k === "m") { addMarker(); e.preventDefault(); }
  else if (k === "f") { $("btn-full").click(); e.preventDefault(); }
});

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => (view === "live" ? liveCharts : historyCharts).forEach((c) => c.render()), 150);
});

/* ================================================================ start */
$("chips").replaceChildren(...Array.from({ length: 10 }, () => { const c = el("div", "chip"); c.append(el("div", "ci"), el("div")); return c; }));
setView(location.hash === "#history" ? "history" : "live");
pollState(); pollHistory(); pollEvents();
setInterval(pollState, 500);
setInterval(pollHistory, 1000);
setInterval(pollEvents, 1000);
setInterval(() => { if (state) renderHero(); setConnection(); }, 1000);
setInterval(() => { if (view === "history") loadHistory(); }, 10000);
