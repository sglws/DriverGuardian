"""Session history database (SQLite): sessions, events and 1 Hz samples. Never images."""

import json
import os
import queue
import sqlite3
import threading
import time

_SCHEMA = """

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_ts REAL NOT NULL,
    ended_ts REAL,
    last_ts REAL,
    label TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    ts REAL NOT NULL, kind TEXT, level TEXT, title TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS samples (
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    ts REAL NOT NULL, risk TEXT, "case" TEXT,
    ear REAL, ear_thr REAL, mar REAL, mar_thr REAL, pitch REAL, yaw REAL, fps REAL,
    flags INTEGER, perclos REAL, blinks INTEGER, yawns INTEGER,
    mq3 INTEGER, mq2 INTEGER, mq3_rel REAL, mq2_rel REAL,
    left_pwm INTEGER, right_pwm INTEGER
);
CREATE INDEX IF NOT EXISTS events_by_session ON events(session_id, ts);
CREATE INDEX IF NOT EXISTS samples_by_session ON samples(session_id, ts);
"""
SAMPLE_FIELDS = ("ts", "risk", "case", "ear", "ear_thr", "mar", "mar_thr", "pitch", "yaw", "fps",
                 "flags", "perclos", "blinks", "yawns", "mq3", "mq2", "mq3_rel", "mq2_rel",
                 "left_pwm", "right_pwm")
_ADDED_COLUMNS = {   # columns added after the first version: older databases get them on start"flags": "INTEGER", "perclos": "REAL", "blinks": "INTEGER", "yawns": "INTEGER",
                  "mq3": "INTEGER", "mq2": "INTEGER", "mq3_rel": "REAL", "mq2_rel": "REAL",
                  "left_pwm": "INTEGER", "right_pwm": "INTEGER"}

FLAG_BITS = {   # the samples' "flags" column: one bit per active condition
    "eyes_closed": 1, "yawning": 2, "looking_away": 4, "head_lean": 8, "phone": 16,
    "eating_drinking": 32, "smoking": 64, "seatbelt_off": 128, "driver_absent": 256, "camera_blocked": 512,
}


class SessionStore:
    """Writes go to a background thread in batches, so the main loop never waits for the SD card."""

    def __init__(self, path: str, keep: int = 20):
        self.path = path
        self.keep = keep
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.Lock()
        self._db = self._connect()
        self._db.executescript(_SCHEMA)
        have = {r["name"] for r in self._db.execute("PRAGMA table_info(samples)")}
        for col, kind in _ADDED_COLUMNS.items():
            if col not in have:
                self._db.execute(f"ALTER TABLE samples ADD COLUMN {col} {kind}")
        self._db.commit()
        self._prune()
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()

    def _connect(self):
        db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.row_factory = sqlite3.Row
        return db

    def _prune(self):
        """Keeps only the newest `keep` sessions."""
        with self._lock:
            self._db.execute("DELETE FROM sessions WHERE id NOT IN "
                             "(SELECT id FROM sessions ORDER BY started_ts DESC LIMIT ?)", (self.keep,))
            self._db.commit()

    def new_session(self, label: str = "") -> int:
        """Written at once, since the caller needs the new id."""
        now = time.time()
        with self._lock:
            cur = self._db.execute("INSERT INTO sessions (started_ts, last_ts, label) VALUES (?, ?, ?)",
                                   (now, now, label))
            self._db.commit()
            new_id = cur.lastrowid
        self._prune()
        return new_id

    def add_event(self, session_id: int, e: dict):
        self._queue.put(("INSERT INTO events (session_id, ts, kind, level, title, detail) VALUES (?,?,?,?,?,?)",
                         (session_id, e["ts"], e["kind"], e["level"], e["title"], e.get("detail", ""))))

    def add_sample(self, session_id: int, s: dict):
        self._queue.put((f"INSERT INTO samples (session_id, {', '.join(chr(34) + f + chr(34) for f in SAMPLE_FIELDS)}) "
                         f"VALUES (?{', ?' * len(SAMPLE_FIELDS)})",
                         (session_id, *[s.get(f) for f in SAMPLE_FIELDS])))
        self._queue.put(("UPDATE sessions SET last_ts = ? WHERE id = ?", (s["ts"], session_id)))

    def update_session(self, session_id: int, **fields):
        allowed = {"label", "notes", "summary", "ended_ts"}
        cols = [k for k in fields if k in allowed]
        if not cols:
            return
        values = [json.dumps(fields[k]) if k == "summary" else fields[k] for k in cols]
        self._queue.put((f"UPDATE sessions SET {', '.join(c + ' = ?' for c in cols)} WHERE id = ?",
                         (*values, session_id)))

    def _writer(self):
        while not self._stop.is_set() or not self._queue.empty():
            try:
                first = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            batch = [first]
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and len(batch) < 500:
                try:
                    batch.append(self._queue.get(timeout=max(0.0, deadline - time.monotonic())))
                except queue.Empty:
                    break
            try:
                with self._lock:
                    for sql, params in batch:
                        self._db.execute(sql, params)
                    self._db.commit()
            except sqlite3.Error as e:
                print(f"[storage] write failed: {e}")

    def flush(self, timeout: float = 5.0):
        end = time.monotonic() + timeout
        while not self._queue.empty() and time.monotonic() < end:
            time.sleep(0.05)
        time.sleep(0.1)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=5)
        with self._lock:
            self._db.close()

    def _read(self, sql, params=()):
        db = self._connect()
        try:
            return [dict(r) for r in db.execute(sql, params)]
        finally:
            db.close()

    def list_sessions(self, limit: int = 200):
        rows = self._read("SELECT s.*, (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id "
                          "AND e.kind = 'marker') AS markers FROM sessions s ORDER BY started_ts DESC LIMIT ?",
                          (limit,))
        for r in rows:
            r["summary"] = json.loads(r["summary"] or "{}")
        return rows

    def get_session(self, session_id: int):
        rows = self._read("SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not rows:
            return None
        s = rows[0]
        s["summary"] = json.loads(s["summary"] or "{}")
        s["events"] = self._read("SELECT id, ts, kind, level, title, detail FROM events "
                                 "WHERE session_id = ? ORDER BY ts, id", (session_id,))
        s["samples"] = self._read(f"SELECT {', '.join(chr(34) + f + chr(34) for f in SAMPLE_FIELDS)} FROM samples "
                                  "WHERE session_id = ? ORDER BY ts", (session_id,))
        return s

    def delete_session(self, session_id: int):
        with self._lock:
            self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._db.commit()
