/* DriverGuardian dashboard - no external libraries (the Pi may be offline). */
"use strict";

const $ = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";

/* ------------------------------------------------------------------ icons */
const ICON_PATHS = {
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.8 2.8L16 10"/>',
  alert: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
  stop: '<path d="M8 3h8l5 5v8l-5 5H8l-5-5V8z"/><path d="m9 9 6 6M15 9l-6 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
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
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  gauge: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m12 18 4-6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
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

/* ------------------------------------------------------------ vocabulary */
const LEVELS = {
  SAFE:    { word: "Safe",    token: "--good",     icon: "check", tone: "good" },
  LOW:     { word: "Low",     token: "--warning",  icon: "info",  tone: "warning" },
  MEDIUM:  { word: "Medium",  token: "--serious",  icon: "alert", tone: "serious" },
  HIGH:    { word: "High",    token: "--critical", icon: "stop",  tone: "critical" },
  WAITING: { word: "Waiting", token: "--neutral",  icon: "clock", tone: "info" },
};
const RISK_ORDER = ["WAITING", "SAFE", "LOW", "MEDIUM", "HIGH"];
const CASES = {
  NONE: "All clear", MICROSLEEP: "Eyes closing", SLEEP: "Driver asleep", YAWN: "Yawning",
  LEAN: "Head leaning", LEAN_PROLONGED: "Prolonged head lean", TURN: "Looking away",
  TURN_PROLONGED: "Prolonged look-away", SEATBELT: "Seatbelt off", PHONE: "Phone use",
  PHONE_REPEAT: "Repeated phone use", CONSUMPTION: "Eating, drinking or smoking",
  CONSUMPTION_REPEAT: "Repeated eating, drinking or smoking", BLOCKED: "Camera blocked",
  ABSENT: "Driver not in seat", PRE_DRIVE: "Waiting for seatbelt", CALIBRATING: "Calibrating",
};
const caseName = (c) => CASES[c] || (c ? c.replace(/_/g, " ").toLowerCase() : "—");
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s);
const fmt = (v, d = 2) => (v == null || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
const signed = (v, d = 1) => (v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d));
function clock(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}
function duration(sec) {
  if (sec == null) return "—";
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  if (h) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

/* ------------------------------------------------------------------ theme */
const THEMES = ["auto", "light", "dark"];
let theme = "auto";
try { theme = localStorage.getItem("dg-theme") || "auto"; } catch (e) { /* storage unavailable */ }
function applyTheme() {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  $("btn-theme").title = `Theme: ${theme === "auto" ? "follows the system" : theme}`;
}
$("btn-theme").onclick = () => {
  theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
  try { localStorage.setItem("dg-theme", theme); } catch (e) { /* ignore */ }
  applyTheme();
};
applyTheme();

/* --------------------------------------------------------------- actions */
$("btn-recal").onclick = async () => {
  if (!confirm("Recalibrate now?\n\nThe driver should sit normally and look straight at the camera, eyes open, for 3 seconds.")) return;
  const b = $("btn-recal"), label = b.querySelector("span");
  try {
    const r = await fetch("/api/recalibrate", { method: "POST", headers: { "X-DriverGuardian": "1" } });
    label.textContent = r.ok ? "Requested" : "Failed";
  } catch (e) { label.textContent = "Failed"; }
  setTimeout(() => { label.textContent = "Recalibrate"; }, 2500);
};
$("btn-snap").onclick = () => {
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  $("btn-snap").download = `driverguardian-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.jpg`;
};
$("btn-full").onclick = () => {
  const box = $("video-box");
  if (document.fullscreenElement) document.exitFullscreen();
  else if (box.requestFullscreen) box.requestFullscreen();
};

/* ------------------------------------------------------------------ video */
const video = $("video");
function startVideo() { video.src = "/stream.mjpg?t=" + Date.now(); }
video.onerror = () => { $("video-wait").hidden = false; setTimeout(startVideo, 2000); };
video.onload = () => { $("video-wait").hidden = true; };
// Started after the page has loaded: an endless MJPEG stream begun earlier
// keeps the browser's loading indicator spinning forever.
if (document.readyState === "complete") startVideo(); else window.addEventListener("load", startVideo);

/* ------------------------------------------------------------------ state */
let state = null;
let lastOk = 0;
let riskSince = { key: null, at: Date.now() };

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function setConnection() {
  const fresh = Date.now() - lastOk < 3000 && state && state.age_sec != null && state.age_sec < 3;
  const c = $("conn");
  c.classList.toggle("live", !!fresh);
  c.classList.toggle("stale", !fresh && lastOk > 0);
  $("conn-text").textContent = fresh ? "Live" : lastOk ? "Reconnecting…" : "Connecting…";
  $("app").classList.toggle("stale-data", !fresh && lastOk > 0);
}

async function pollState() {
  try {
    state = await getJSON("/api/state");
    lastOk = Date.now();
    render();
  } catch (e) { /* keep the last render, marked stale */ }
  setConnection();
}

function render() {
  if (!state || !state.risk) return;
  if (video.naturalWidth > 0) $("video-wait").hidden = true;
  renderHero();
  renderChips();
  renderPanels();
  $("video-fps").textContent = state.perf && state.perf.fps != null ? `${fmt(state.perf.fps, 1)} FPS` : "";
  const cal = $("calib");
  cal.hidden = !state.calibrating;
  $("calib-bar").style.width = `${Math.round((state.calib_progress || 0) * 100)}%`;
  const sess = state.session || {};
  $("uptime").textContent = sess.uptime_s != null ? `Session ${duration(sess.uptime_s)}` : "";
}

function renderHero() {
  const lv = LEVELS[state.risk] || LEVELS.WAITING;
  const key = `${state.risk}`;
  if (riskSince.key !== key) riskSince = { key, at: Date.now() };
  const hero = $("hero");
  hero.style.setProperty("--level", `var(${lv.token})`);
  const ic = $("hero-icon");
  ic.replaceChildren(icon(lv.icon));
  $("hero-level").textContent = state.calibrating ? "Calibrating" : lv.word;
  $("hero-case").textContent = caseName(state.case);
  $("hero-msg").textContent = (state.messages || [])[0] || "";
  $("hero-for").textContent = duration((Date.now() - riskSince.at) / 1000);
  $("hero-score").textContent = state.score != null ? state.score : "—";
  const rate = state.perf && state.perf.rate_hz;
  $("hero-rate").textContent = rate != null ? `${fmt(rate, 1)} Hz` : "—";
}

/* chips: [key, icon, label, value, extra, tone] */
function renderChips() {
  const s = state, e = s.eyes, m = s.mouth, h = s.head, o = s.objects || {}, cam = s.camera || {};
  const rows = [];
  if (e) {
    const closedLong = e.closed && e.closed_sec >= 1;
    rows.push(["eyes", e.closed ? "eyeOff" : "eye", "Eyes",
      e.looking_down ? "Looking down" : e.closed ? `Closed ${fmt(e.closed_sec, 1)} s` : "Open",
      `EAR ${fmt(e.ear)} · limit ${fmt(e.ear_thr)}`, closedLong ? "crit" : e.closed ? "warn" : "ok"]);
    rows.push(["blinks", "blink", "Blinks", `${e.blink_rate} in last ${Math.round(e.blink_window_sec)} s`,
      `${e.blinks_total} in session`, e.level === "DROWSY" ? "warn" : ""]);
  } else {
    rows.push(["eyes", "eye", "Eyes", "—", s.calibrating ? "calibrating" : "no face", ""]);
    rows.push(["blinks", "blink", "Blinks", "—", "", ""]);
  }
  if (m) {
    rows.push(["mouth", "mouth", "Mouth", m.yawning ? "Yawning" : m.open ? "Open" : "Closed",
      `MAR ${fmt(m.mar)} · ${m.yawns_total} yawn${m.yawns_total === 1 ? "" : "s"}`, m.yawning ? "warn" : "ok"]);
  } else rows.push(["mouth", "mouth", "Mouth", "—", "", ""]);
  if (h) {
    const dir = [h.pitch_label !== "FORWARD" ? cap(h.pitch_label.replace("/", " / ")) : null,
                 h.yaw_label !== "CENTER" ? cap(h.yaw_label) : null].filter(Boolean).join(", ") || "Forward";
    const tone = h.turn_risk === "HIGH" ? "crit" : (h.turn_risk !== "NONE" || h.lean_sec > 0) ? "warn" : "ok";
    rows.push(["head", "head", "Head", dir, `pitch ${signed(h.pitch)}°  yaw ${signed(h.yaw)}°`, tone]);
  } else rows.push(["head", "head", "Head", "—", "", ""]);
  const det = (v) => (v == null ? "Not supported" : v ? "Detected" : "Not detected");
  rows.push(["phone", "phone", "Phone", det(o.phone), "", o.phone ? "crit" : o.phone === false ? "ok" : ""]);
  rows.push(["consume", "cup", "Eating / drinking", det(o.consumption), "", o.consumption ? "warn" : o.consumption === false ? "ok" : ""]);
  rows.push(["smoke", "smoke", "Smoking", det(o.cigarette), "", o.cigarette ? "warn" : o.cigarette === false ? "ok" : ""]);
  const sb = o.seatbelt;
  rows.push(["belt", "belt", "Seatbelt", sb === "ON" ? "On" : sb === "OFF" ? "Off" : sb === "N/A" ? "Not supported" : "Not seen yet",
    "", sb === "OFF" ? "crit" : sb === "ON" ? "ok" : "warn"]);
  const pres = s.presence;
  rows.push(["driver", "user", "Driver", pres === "DRIVER_PRESENT" ? "Present" : pres === "DRIVER_ABSENT" ? "Not in seat"
    : pres === "CAMERA_BLOCKED" ? "Camera blocked" : "—", s.face_found ? "face tracked" : "no face",
    pres && pres !== "DRIVER_PRESENT" ? "crit" : pres ? "ok" : ""]);
  rows.push(["cam", "sun", "Lighting", cam.low_light ? "Low light" : "Normal",
    `brightness ${cam.brightness != null ? cam.brightness : "—"}${cam.low_light ? ", enhanced" : ""}`, cam.low_light ? "warn" : ""]);

  const box = $("chips");
  if (box.children.length !== rows.length) {
    box.replaceChildren(...rows.map(() => {
      const c = el("div", "chip"); c.append(el("div", "ci"), el("div"));
      return c;
    }));
  }
  rows.forEach(([key, ic, label, value, extra, tone], i) => {
    const c = box.children[i];
    c.className = `chip ${tone || ""}`;
    const ci = c.children[0];
    if (ci.dataset.icon !== ic) { ci.replaceChildren(icon(ic)); ci.dataset.icon = ic; }
    const body = c.children[1];
    body.replaceChildren(el("div", "ck", label), el("div", "cv", value));
    if (extra) body.append(el("div", "cx", extra));
  });
}

/* ------------------------------------------------------------------ panels */
function statusBadge(ok, goodText, badText, neutral) {
  const tone = neutral ? "neutral" : ok ? "good" : "crit";
  const s = el("span", `status ${tone}`);
  s.append(icon(neutral ? "info" : ok ? "check" : "stop"), document.createTextNode(neutral ? neutral : ok ? goodText : badText));
  return s;
}
function kvRow(parent, iconName, label, valueNode, small) {
  const k = el("div", "k"); k.append(icon(iconName), document.createTextNode(label));
  const v = el("div", "v");
  if (typeof valueNode === "string") v.textContent = valueNode; else v.append(valueNode);
  if (small) v.append(el("small", null, small));
  parent.append(k, v);
}
const STAGE_NAMES = {
  camera: "Camera (incl. waiting for frame)", preprocess: "Pre-processing", mediapipe: "Face mesh",
  presence_logic: "Presence & timers", yolo: "YOLO hand-off", risk_draw: "Risk & overlay",
  imshow: "Local window", waitkey: "Window events",
};

function renderPanels() {
  const s = state, perf = s.perf || {}, req = s.requirements || {}, sys = s.system, links = s.links || {};

  // Requirements & performance
  const pr = $("p-req"); pr.replaceChildren();
  const kv = el("div", "kv");
  const rate = perf.rate_hz, gap = perf.gap_session_ms;
  kvRow(kv, "gauge", `Average update rate (≥ ${req.min_avg_rate_hz} Hz)`,
    rate == null ? statusBadge(false, "", "", "measuring…") : statusBadge(rate >= req.min_avg_rate_hz, `${fmt(rate, 1)} Hz`, `${fmt(rate, 1)} Hz`));
  kvRow(kv, "clock", `Longest gap this session (≤ ${Math.round(req.max_gap_ms)} ms)`,
    gap == null ? statusBadge(false, "", "", "measuring…") : statusBadge(gap <= req.max_gap_ms, `${Math.round(gap)} ms`, `${Math.round(gap)} ms`));
  kvRow(kv, "bolt", "Processing rate", `${fmt(perf.fps, 1)} FPS`, perf.camera_fps ? `camera ${perf.camera_fps}` : "");
  pr.append(kv);
  const stages = perf.stages_ms || {};
  const names = Object.keys(stages);
  if (names.length) {
    pr.append(el("hr", "sep"), el("div", "sub-h", "Time per frame"));
    const total = names.reduce((a, k) => a + stages[k], 0) || 1;
    const bars = el("div", "bars");
    names.forEach((k) => {
      const track = el("div", "track"), fill = el("div", "fill");
      fill.style.width = `${Math.max(0.5, (stages[k] / total) * 100)}%`;
      track.append(fill);
      bars.append(el("div", "n", STAGE_NAMES[k] || k), track, el("div", "val", `${fmt(stages[k], 1)} ms`));
    });
    pr.append(bars);
  }

  // System health
  const ps = $("p-sys"); ps.replaceChildren();
  const kv2 = el("div", "kv");
  if (sys) {
    const t = sys.temp_c, thr = (sys.throttled || []).length > 0;
    if (t != null) {
      const tone = thr ? "crit" : t >= 80 ? "crit" : t >= 70 ? "warn" : "good";
      const b = el("span", `status ${tone}`);
      b.append(icon(tone === "good" ? "check" : tone === "warn" ? "alert" : "stop"), document.createTextNode(`${fmt(t, 1)} °C${thr ? " · throttling" : ""}`));
      kvRow(kv2, "temp", "CPU temperature", b);
    }
    if (sys.load1 != null) kvRow(kv2, "cpu", "CPU load", `${fmt(sys.load1, 2)}`, `of ${sys.cores} cores`);
    if (sys.mem_available_mb != null) kvRow(kv2, "memory", "Memory available", `${fmt(sys.mem_available_mb / 1024, 1)} GB`,
      sys.swap_used_mb > 50 ? `swap ${Math.round(sys.swap_used_mb)} MB` : "");
    if (sys.rss_mb != null) kvRow(kv2, "box", "App memory", `${Math.round(sys.rss_mb)} MB`, `${sys.threads} threads`);
  } else {
    kv2.append(el("div", "k", "System readings appear on the Raspberry Pi"), el("div", "v", ""));
  }
  ps.append(kv2, el("hr", "sep"), el("div", "sub-h", "Components"));
  const kv3 = el("div", "kv");
  const comp = (v, good) => {
    const tone = v === good ? "good" : v === "disabled" || v === "off" || v === "unsupported" ? "neutral" : "warn";
    const b = el("span", `status ${tone}`);
    b.append(icon(tone === "good" ? "check" : tone === "warn" ? "alert" : "info"), document.createTextNode(cap(v || "—")));
    return b;
  };
  kvRow(kv3, "box", "Object detection (YOLO)", comp(links.yolo, "running"),
    links.yolo_age != null && links.yolo === "running" ? `${fmt(links.yolo_age, 1)} s ago` : "");
  kvRow(kv3, "bt", "ESP32 link", comp(links.esp32, "connected"));
  kvRow(kv3, "voice", "Voice alerts", comp(links.voice, "on"));
  if (links.voice_last) {
    const q = el("div", "quote", `“${links.voice_last}”`);
    if (links.voice_last_age != null) q.append(el("small", null, `${duration(links.voice_last_age)} ago`));
    kv3.append(q);
  }
  kvRow(kv3, "users", "Dashboard viewers", String(s.viewers != null ? s.viewers : 0));
  ps.append(kv3);

  // Session
  const pn = $("p-session"); pn.replaceChildren();
  const sess = s.session || {};
  if (sess.started_ts) $("session-start").textContent = `since ${clock(sess.started_ts)}`;
  pn.append(el("div", "big", duration(sess.uptime_s)));
  const tin = sess.time_in || {};
  const tot = RISK_ORDER.reduce((a, r) => a + (tin[r] || 0), 0);
  pn.append(el("div", "sub-h", "Time by risk level"));
  const stack = el("div", "stack");
  stack.setAttribute("role", "img");
  stack.setAttribute("aria-label", RISK_ORDER.map((r) => `${LEVELS[r].word} ${tot ? Math.round((tin[r] || 0) / tot * 100) : 0}%`).join(", "));
  const legend = el("div", "stack-legend");
  RISK_ORDER.forEach((r) => {
    const share = tot ? (tin[r] || 0) / tot : 0;
    if (share > 0) {
      const seg = el("i"); seg.style.width = `${share * 100}%`; seg.style.background = `var(${LEVELS[r].token})`;
      seg.title = `${LEVELS[r].word}: ${duration(tin[r])} (${Math.round(share * 100)}%)`;
      stack.append(seg);
    }
    const k = el("div", "k");
    const ic = icon(LEVELS[r].icon); ic.style.color = `var(${LEVELS[r].token})`;
    k.append(ic, document.createTextNode(LEVELS[r].word), el("b", null, `${Math.round(share * 100)}%`));
    legend.append(k);
  });
  pn.append(stack, legend);
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

/* ---------------------------------------------------------------- history */
let samples = [];
let lastT = -1;
let rangeSec = 300;

async function pollHistory() {
  try {
    const h = await getJSON(`/api/history?since=${lastT}`);
    if (h.samples.length) {
      samples.push(...h.samples);
      lastT = samples[samples.length - 1].t;
      const cutoff = lastT - (h.window_sec || 600);
      let i = 0;
      while (i < samples.length && samples[i].t < cutoff) i++;
      if (i) samples = samples.slice(i);
    }
    charts.forEach((c) => c.render());
  } catch (e) { /* keep last render */ }
}

document.querySelectorAll("#range button").forEach((b) => {
  b.onclick = () => {
    rangeSec = Number(b.dataset.sec);
    document.querySelectorAll("#range button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    charts.forEach((c) => c.render());
  };
});

function visible() {
  if (!samples.length) return { rows: [], t0: 0, t1: 0 };
  const t1 = samples[samples.length - 1].t, t0 = t1 - rangeSec;
  let lo = 0, hi = samples.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (samples[mid].t < t0) lo = mid + 1; else hi = mid; }
  return { rows: samples.slice(lo), t0, t1 };
}
function niceTicks(min, max, count = 4) {
  if (min === max) { min -= 1; max += 1; }
  const span = max - min, step0 = span / count, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count + 0.5) || mag * 10;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, ticks = [];
  for (let v = lo; v <= hi + step * 0.001; v += step) ticks.push(+v.toFixed(10));
  return { lo, hi, ticks, step };
}
function xTicks(t0, t1) {
  const span = t1 - t0, step = span <= 60 ? 15 : span <= 300 ? 60 : 120, out = [];
  for (let back = 0; back <= span + 0.01; back += step) out.push({ t: t1 - back, label: back === 0 ? "now" : step < 60 ? `−${back}s` : `−${back / 60}m` });
  return out;
}
function svgEl(tag, attrs) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
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
  const rect = card.getBoundingClientRect();
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  let x = rect.left + window.scrollX + px + 14, y = rect.top + window.scrollY + py - th - 10;
  if (x + tw > window.scrollX + document.documentElement.clientWidth - 8) x = rect.left + window.scrollX + px - tw - 14;
  if (y < window.scrollY + 8) y = rect.top + window.scrollY + py + 14;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`;
}
function hideTip() { tip.style.display = "none"; }

/* A card with title, optional legend, plot and a table-view toggle. */
function chartShell(card, title, sub, legendItems) {
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
  const body = el("div", "card-b");
  const plot = el("div", "chart");
  const tableWrap = el("div", "table-wrap"); tableWrap.hidden = true;
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

/* Line chart (one y-axis, shared unit). */
function lineChart(card, cfg) {
  const shell = chartShell(card, cfg.title, cfg.sub,
    cfg.series.length > 1 ? cfg.series.map((s) => ({ token: s.token, label: s.label })) : null);
  let hoverIdx = null, geom = null;
  const H = 170, pad = { l: 40, r: cfg.series.length > 1 ? 44 : 14, t: 10, b: 24 };

  function render() {
    const { rows, t0, t1 } = visible();
    if (shell.showTable) {
      const recent = rows.slice(-40).reverse();
      renderTable(shell.tableWrap, ["Time", ...cfg.series.map((s) => `${s.label}${cfg.unit ? ` (${cfg.unit})` : ""}`), ...(cfg.ref ? [cfg.ref.label] : [])],
        recent.map((r) => [clock(r.ts), ...cfg.series.map((s) => fmt(r[s.key], cfg.digits)), ...(cfg.ref ? [fmt(r[cfg.ref.key], cfg.digits)] : [])]));
      return;
    }
    const W = shell.plot.clientWidth || 300;
    const vals = [];
    rows.forEach((r) => { cfg.series.forEach((s) => { if (r[s.key] != null) vals.push(r[s.key]); }); if (cfg.ref && r[cfg.ref.key] != null) vals.push(r[cfg.ref.key]); });
    if (cfg.includeZero) vals.push(0);
    const svg = svgEl("svg", { class: "plot", viewBox: `0 0 ${W} ${H}`, height: H, role: "img",
      "aria-label": `${cfg.title} over the last ${rangeSec / 60} minutes` });
    if (!vals.length) {
      shell.plot.replaceChildren(el("div", "empty", "No data yet — waiting for the driver's face"));
      geom = null; return;
    }
    let min = Math.min(...vals), max = Math.max(...vals);
    if (cfg.minSpan && max - min < cfg.minSpan) { const c = (max + min) / 2; min = c - cfg.minSpan / 2; max = c + cfg.minSpan / 2; }
    if (cfg.floor != null && min < cfg.floor) { max += cfg.floor - min; min = cfg.floor; }
    const yt = niceTicks(min, max, 4);
    if (cfg.floor != null && yt.lo < cfg.floor) yt.ticks = yt.ticks.filter((v) => v >= cfg.floor), yt.lo = cfg.floor;
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const x = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * pw;
    const y = (v) => pad.t + (1 - (v - yt.lo) / (yt.hi - yt.lo)) * ph;
    yt.ticks.forEach((v) => {
      svg.append(svgEl("line", { class: v === 0 && cfg.includeZero ? "baseline" : "gridline", x1: pad.l, x2: W - pad.r, y1: y(v), y2: y(v) }));
      const tx = svgEl("text", { class: "tick", x: pad.l - 6, y: y(v) + 3.5, "text-anchor": "end" });
      tx.textContent = Math.abs(yt.step) < 1 ? v.toFixed(2) : String(Math.round(v));
      svg.append(tx);
    });
    svg.append(svgEl("line", { class: "baseline", x1: pad.l, x2: W - pad.r, y1: pad.t + ph, y2: pad.t + ph }));
    xTicks(t0, t1).forEach((tk) => {
      const tx = svgEl("text", { class: "tick", x: x(tk.t), y: H - 6, "text-anchor": tk.label === "now" ? "end" : "middle" });
      tx.textContent = tk.label; svg.append(tx);
    });
    const pathFor = (key) => {
      let d = "", prevT = null;
      rows.forEach((r) => {
        const v = r[key];
        if (v == null) { prevT = null; return; }
        d += (prevT == null || r.t - prevT > 1.5 ? "M" : "L") + x(r.t).toFixed(1) + "," + y(v).toFixed(1);
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
          lbl.textContent = `${cfg.ref.label} ${fmt(last[cfg.ref.key], cfg.digits)}`;
          svg.append(lbl);
        }
      }
    }
    const endYs = [];
    cfg.series.forEach((s) => {
      svg.append(svgEl("path", { d: pathFor(s.key), class: "line", style: `stroke:var(${s.token})` }));
      if (cfg.series.length > 1) {
        const last = [...rows].reverse().find((r) => r[s.key] != null);
        if (last) endYs.push({ s, yy: y(last[s.key]) });
      }
    });
    // direct end labels only when they don't collide (legend always present)
    if (endYs.length === 2 && Math.abs(endYs[0].yy - endYs[1].yy) >= 13) {
      endYs.forEach(({ s, yy }) => {
        const t = svgEl("text", { class: "end-label", x: W - pad.r + 6, y: yy + 4 });
        t.textContent = s.short || s.label; svg.append(t);
      });
    }
    const hover = svgEl("g", {});
    svg.append(hover);
    const hit = svgEl("rect", { x: pad.l, y: pad.t, width: pw, height: ph, fill: "transparent", tabindex: "0",
      "aria-label": `${cfg.title} chart: use left and right arrow keys to read values` });
    svg.append(hit);
    geom = { rows, x, y, hover, card };
    const at = (i) => {
      if (!geom || !rows.length) return;
      i = Math.max(0, Math.min(rows.length - 1, i)); hoverIdx = i;
      const r = rows[i], cx = x(r.t);
      hover.replaceChildren(svgEl("line", { class: "xhair", x1: cx, x2: cx, y1: pad.t, y2: pad.t + ph }));
      const tipRows = [];
      cfg.series.forEach((s) => {
        if (r[s.key] != null) {
          hover.append(svgEl("circle", { class: "hover-dot", cx, cy: y(r[s.key]), r: 4, style: `fill:var(${s.token})` }));
        }
        tipRows.push([`var(${s.token})`, r[s.key] == null ? "—" : `${fmt(r[s.key], cfg.digits)}${cfg.unit ? " " + cfg.unit : ""}`, s.label]);
      });
      if (cfg.ref && r[cfg.ref.key] != null) tipRows.push(["var(--muted)", fmt(r[cfg.ref.key], cfg.digits), cfg.ref.label]);
      const svgRect = svg.getBoundingClientRect(), cardRect = card.getBoundingClientRect();
      showTip(card, (svgRect.left - cardRect.left) + cx * (svgRect.width / W), (svgRect.top - cardRect.top) + pad.t + 10, clock(r.ts), tipRows);
    };
    const nearest = (evt) => {
      const rect = svg.getBoundingClientRect(), px = (evt.clientX - rect.left) * (W / rect.width);
      const t = t0 + ((px - pad.l) / pw) * (t1 - t0);
      let lo = 0, hi = rows.length - 1;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (rows[mid].t < t) lo = mid + 1; else hi = mid; }
      if (lo > 0 && Math.abs(rows[lo - 1].t - t) < Math.abs(rows[lo].t - t)) lo--;
      return lo;
    };
    hit.addEventListener("pointermove", (e) => at(nearest(e)));
    hit.addEventListener("pointerleave", () => { hoverIdx = null; hover.replaceChildren(); hideTip(); });
    hit.addEventListener("focus", () => at(rows.length - 1));
    hit.addEventListener("blur", () => { hoverIdx = null; hover.replaceChildren(); hideTip(); });
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { at((hoverIdx ?? rows.length - 1) - (e.shiftKey ? 20 : 1)); e.preventDefault(); }
      if (e.key === "ArrowRight") { at((hoverIdx ?? rows.length - 1) + (e.shiftKey ? 20 : 1)); e.preventDefault(); }
      if (e.key === "Escape") hit.blur();
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  return { render };
}

/* Risk timeline: one row of status-coloured segments (icon + label legend). */
function riskChart(card) {
  const shell = chartShell(card, "Risk timeline", "risk level over time",
    RISK_ORDER.map((r) => ({ icon: LEVELS[r].icon, token: LEVELS[r].token, label: LEVELS[r].word })));
  const H = 64, pad = { l: 14, r: 14, t: 8, b: 24 };
  function segments(rows) {
    const segs = [];
    rows.forEach((r) => {
      const last = segs[segs.length - 1];
      if (last && last.risk === r.risk && last.case === r.case && r.t - last.end <= 1.5) last.end = r.t;
      else segs.push({ risk: r.risk, case: r.case, start: r.t, end: r.t, ts: r.ts });
    });
    return segs;
  }
  function render() {
    const { rows, t0, t1 } = visible();
    const segs = segments(rows);
    if (shell.showTable) {
      renderTable(shell.tableWrap, ["Started", "Duration", "Level", "Reason"],
        segs.slice().reverse().slice(0, 60).map((s) => [clock(s.ts), duration(s.end - s.start + 0.25),
          (LEVELS[s.risk] || LEVELS.WAITING).word, caseName(s.case)]));
      return;
    }
    const W = shell.plot.clientWidth || 300;
    if (!rows.length) { shell.plot.replaceChildren(el("div", "empty", "No data yet")); return; }
    const svg = svgEl("svg", { class: "plot", viewBox: `0 0 ${W} ${H}`, height: H, role: "img",
      "aria-label": `Risk timeline over the last ${rangeSec / 60} minutes` });
    const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const x = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * pw;
    svg.append(svgEl("rect", { x: pad.l, y: pad.t, width: pw, height: ph, rx: 4, style: "fill:var(--surface-2)" }));
    segs.forEach((s) => {
      let x0 = x(s.start), x1 = x(s.end + 0.25);
      if (x1 - x0 > 3) { x0 += 1; x1 -= 1; }   // 2px surface gap between neighbours
      svg.append(svgEl("rect", { x: x0, y: pad.t, width: Math.max(1, x1 - x0), height: ph, rx: 3,
        style: `fill:var(${(LEVELS[s.risk] || LEVELS.WAITING).token})` }));
    });
    xTicks(t0, t1).forEach((tk) => {
      const tx = svgEl("text", { class: "tick", x: x(tk.t), y: H - 6, "text-anchor": tk.label === "now" ? "end" : "middle" });
      tx.textContent = tk.label; svg.append(tx);
    });
    const hover = svgEl("g", {}); svg.append(hover);
    const hit = svgEl("rect", { x: pad.l, y: 0, width: pw, height: pad.t + ph + 4, fill: "transparent", tabindex: "0",
      "aria-label": "Risk timeline: use left and right arrow keys to step through segments" });
    svg.append(hit);
    let idx = null;
    const at = (i) => {
      if (!segs.length) return;
      idx = Math.max(0, Math.min(segs.length - 1, i));
      const s = segs[idx], cx = (x(s.start) + x(s.end + 0.25)) / 2;
      hover.replaceChildren(svgEl("rect", { x: x(s.start), y: pad.t - 2, width: Math.max(2, x(s.end + 0.25) - x(s.start)),
        height: ph + 4, rx: 4, fill: "none", style: "stroke:var(--ink);stroke-width:1.5" }));
      const svgRect = svg.getBoundingClientRect(), cardRect = card.getBoundingClientRect();
      showTip(card, (svgRect.left - cardRect.left) + cx * (svgRect.width / W), svgRect.top - cardRect.top + pad.t,
        `${clock(s.ts)} · ${duration(s.end - s.start + 0.25)}`,
        [[`var(${(LEVELS[s.risk] || LEVELS.WAITING).token})`, (LEVELS[s.risk] || LEVELS.WAITING).word, caseName(s.case)]]);
    };
    hit.addEventListener("pointermove", (e) => {
      const rect = svg.getBoundingClientRect(), px = (e.clientX - rect.left) * (W / rect.width);
      const t = t0 + ((px - pad.l) / pw) * (t1 - t0);
      let i = segs.findIndex((s) => t <= s.end + 0.25);
      if (i < 0) i = segs.length - 1;
      at(i);
    });
    hit.addEventListener("pointerleave", () => { hover.replaceChildren(); hideTip(); });
    hit.addEventListener("focus", () => at(segs.length - 1));
    hit.addEventListener("blur", () => { hover.replaceChildren(); hideTip(); });
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { at((idx ?? segs.length - 1) - 1); e.preventDefault(); }
      if (e.key === "ArrowRight") { at((idx ?? segs.length - 1) + 1); e.preventDefault(); }
      if (e.key === "Escape") hit.blur();
    });
    shell.plot.replaceChildren(svg);
  }
  shell.onToggle = render;
  return { render };
}

const charts = [
  riskChart($("c-risk")),
  lineChart($("c-ear"), { title: "Eye openness", sub: "eye aspect ratio (EAR)", digits: 3, minSpan: 0.1, floor: 0,
    series: [{ key: "ear", label: "EAR", token: "--series-1" }], ref: { key: "ear_thr", label: "closed below" } }),
  lineChart($("c-mar"), { title: "Mouth opening", sub: "mouth aspect ratio (MAR)", digits: 3, minSpan: 0.1, floor: 0,
    series: [{ key: "mar", label: "MAR", token: "--series-1" }], ref: { key: "mar_thr", label: "open above" } }),
  lineChart($("c-head"), { title: "Head pose", sub: "change from calibrated position", unit: "°", digits: 1,
    includeZero: true, minSpan: 20,
    series: [{ key: "pitch", label: "Pitch (down +)", short: "Pitch", token: "--series-1" },
             { key: "yaw", label: "Yaw (right +)", short: "Yaw", token: "--series-2" }] }),
];

let resizeTimer = null;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => charts.forEach((c) => c.render()), 150); });

/* ------------------------------------------------------------------ events */
let events = [];
let lastEventId = 0;
let evFilter = "all";
const EV_ICON = { good: "check", warning: "alert", serious: "alert", critical: "stop" };
const KIND_ICON = { voice: "voice", system: "cpu", detect: "camera", risk: "info" };

async function pollEvents() {
  try {
    const r = await getJSON(`/api/events?since=${lastEventId}`);
    if (r.events.length) {
      events.push(...r.events);
      lastEventId = events[events.length - 1].id;
      if (events.length > 300) events = events.slice(-300);
      renderEvents();
    }
  } catch (e) { /* keep */ }
}
function renderEvents() {
  const list = $("events");
  const shown = events.filter((e) => evFilter === "all" || e.kind === evFilter)
    .slice().sort((a, b) => b.ts - a.ts || b.id - a.id);
  $("ev-count").textContent = `${shown.length} event${shown.length === 1 ? "" : "s"}`;
  if (!shown.length) { list.replaceChildren(el("div", "empty", "Nothing logged yet")); return; }
  list.replaceChildren(...shown.map((e) => {
    const row = el("div", `event ${e.level}`);
    const t = el("time", null, clock(e.ts));
    t.setAttribute("datetime", new Date(e.ts * 1000).toISOString());
    const ic = el("div", "ei"); ic.append(icon(EV_ICON[e.level] || KIND_ICON[e.kind] || "info"));
    const body = el("div"); body.append(el("div", "et", e.title));
    if (e.detail) body.append(el("div", "ed", e.detail));
    row.append(t, ic, body);
    return row;
  }));
}
document.querySelectorAll("#ev-filters button").forEach((b) => {
  b.onclick = () => {
    evFilter = b.dataset.kind;
    document.querySelectorAll("#ev-filters button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    renderEvents();
  };
});

/* ------------------------------------------------------------------- loop */
pollState(); pollHistory(); pollEvents();
setInterval(pollState, 500);
setInterval(pollHistory, 1000);
setInterval(pollEvents, 1000);
setInterval(() => { if (state) renderHero(); setConnection(); }, 1000);
