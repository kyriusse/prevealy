#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse
import html
import datetime
import sys


# -------------------------
# Paths (robust in CGI)
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "events.db")

COOKIE_NAME = "liked_events"
COOKIE_MAX_AGE = 31536000  # 1 year


def esc(s):
    """Escape HTML entities safely"""
    return html.escape("" if s is None else str(s))


def get_params():
    """Get all query parameters"""
    qs = os.environ.get("QUERY_STRING", "")
    return urllib.parse.parse_qs(qs, keep_blank_values=True)


def get_param(name, default=""):
    """Get single query parameter"""
    params = get_params()
    return params.get(name, [default])[0]


def qident(name):
    """Quote sqlite identifier safely"""
    return '"' + (name or "").replace('"', '""') + '"'


# -------------------------
# DB init / migration
# -------------------------
def table_exists(cur, name):
    """Check if table exists"""
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def get_columns(cur, table):
    """Get column names for a table"""
    cur.execute("PRAGMA table_info(%s)" % qident(table))
    return [r[1] for r in cur.fetchall()]


def ensure_column(cur, table, col_name, col_def):
    """Add column if it doesn't exist"""
    cols = [c.lower() for c in get_columns(cur, table)]
    if col_name.lower() not in cols:
        cur.execute("ALTER TABLE %s ADD COLUMN %s %s" % (qident(table), qident(col_name), col_def))


def init_db():
    """Initialize database and ensure schema is up to date"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # events table (base)
        if not table_exists(cur, "events"):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    event_date TEXT,
                    event_time TEXT,
                    location TEXT,
                    created_at TEXT NOT NULL
                )
            """)

        # migrate columns if older DB
        ensure_column(cur, "events", "identity_mode", "TEXT")
        ensure_column(cur, "events", "identity_pseudo", "TEXT")
        ensure_column(cur, "events", "likes", "INTEGER DEFAULT 0")

        # settings table (for Identifier pseudo)
        if not table_exists(cur, "settings"):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

        # indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_title ON events(title)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)")

        conn.commit()
        conn.close()
    except Exception as e:
        print("Content-Type: text/html; charset=utf-8\n\n")
        print("<h2>Database initialization error</h2>")
        print("<pre>%s</pre>" % esc(str(e)))
        sys.exit(1)


# -------------------------
# Cookies helpers
# -------------------------
def parse_cookie_header():
    """Parse HTTP Cookie header"""
    raw = os.environ.get("HTTP_COOKIE", "") or ""
    out = {}
    parts = raw.split(";")
    for p in parts:
        p = p.strip()
        if not p or "=" not in p:
            continue
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def get_liked_ids():
    """Get set of liked event IDs from cookie"""
    cookies = parse_cookie_header()
    val = cookies.get(COOKIE_NAME, "")
    if not val:
        return set()

    try:
        val = urllib.parse.unquote(val)
    except Exception:
        pass

    liked = set()
    for part in val.split(","):
        part = part.strip()
        if part.isdigit():
            liked.add(int(part))
    return liked


def build_set_cookie(liked_ids_set):
    """Build Set-Cookie header value"""
    liked_list = sorted(list(liked_ids_set))[-350:]  # Keep only last 350
    val = ",".join([str(x) for x in liked_list])
    val = urllib.parse.quote(val)
    return "%s=%s; Path=/; Max-Age=%d; SameSite=Lax; HttpOnly" % (COOKIE_NAME, val, COOKIE_MAX_AGE)


# -------------------------
# Settings helpers
# -------------------------
def get_setting(key, default=""):
    """Get setting value from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] is not None else default
    except Exception:
        return default


def set_setting(key, value):
    """Set setting value in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        conn.commit()
        conn.close()
    except Exception as e:
        print("<!-- Error setting value: %s -->" % esc(str(e)))


# -------------------------
# BDD logic
# -------------------------
def insert_event(ev_type, title, description, event_date, event_time, location, identity_mode, identity_pseudo):
    """Insert new event into database"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    description = (description or "").strip()
    event_date = (event_date or "").strip()
    event_time = (event_time or "").strip()
    location = (location or "").strip()
    identity_mode = (identity_mode or "").strip()
    identity_pseudo = (identity_pseudo or "").strip()

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO events(type, title, description, event_date, event_time, location, created_at, identity_mode, identity_pseudo, likes)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            ev_type,
            title.strip(),
            description if description else None,
            event_date if event_date else None,
            event_time if event_time else None,
            location if location else None,
            now,
            identity_mode if identity_mode else None,
            identity_pseudo if identity_pseudo else None
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print("<!-- Error inserting event: %s -->" % esc(str(e)))


def delete_event(event_id):
    """Delete event from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("<!-- Error deleting event: %s -->" % esc(str(e)))


def like_event(event_id):
    """Increment like count for event"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE events SET likes = COALESCE(likes, 0) + 1 WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("<!-- Error liking event: %s -->" % esc(str(e)))


def search_events(q, type_filter):
    """Search events with optional filters"""
    q = (q or "").strip()
    type_filter = (type_filter or "").strip()

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        where = []
        params = []

        if type_filter:
            where.append("type = ?")
            params.append(type_filter)

        if q:
            like = "%" + q + "%"
            where.append("(type LIKE ? OR title LIKE ? OR description LIKE ? OR location LIKE ? OR event_date LIKE ? OR identity_mode LIKE ? OR identity_pseudo LIKE ?)")
            params.extend([like, like, like, like, like, like, like])

        sql = """
            SELECT id, type, title, description, event_date, event_time, location, created_at,
                   identity_mode, identity_pseudo, COALESCE(likes,0)
            FROM events
        """

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += """
            ORDER BY
                CASE WHEN event_date IS NULL THEN 1 ELSE 0 END,
                event_date DESC,
                created_at DESC
            LIMIT 50
        """

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print("<!-- Error searching events: %s -->" % esc(str(e)))
        return []


# -------------------------
# MAIN
# -------------------------
init_db()

msg = ""
q = get_param("q", "")
type_filter = get_param("type_filter", "")
show_add = get_param("add", "0")
show_identity = get_param("identity", "0")

identifier_pseudo = get_setting("identifier_pseudo", "").strip()

liked_ids = get_liked_ids()
set_cookie_header_value = None

method = os.environ.get("REQUEST_METHOD", "GET").upper()

if method == "POST":
    try:
        size = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
    except Exception:
        size = 0

    data = sys.stdin.read(size) if size > 0 else ""
    post = urllib.parse.parse_qs(data, keep_blank_values=True)
    post_action = post.get("post_action", [""])[0]

    if post_action == "save_identifier":
        new_pseudo = (post.get("identifier_pseudo", [""])[0] or "").strip()
        if not new_pseudo:
            msg = "Identifier pseudo is required."
            show_identity = "1"
        else:
            set_setting("identifier_pseudo", new_pseudo)
            identifier_pseudo = new_pseudo
            msg = "Identifier saved."
            show_identity = "0"

    elif post_action == "save_event":
        ev_type = post.get("type", ["I SEE..."])[0]
        title = post.get("title", [""])[0]
        description = post.get("description", [""])[0]
        event_date = post.get("event_date", [""])[0]
        event_time = post.get("event_time", [""])[0]
        location = post.get("location", [""])[0]

        identity_mode = (post.get("identity_mode", ["Anonymous"])[0] or "").strip()
        pseudo_input = (post.get("identity_pseudo", [""])[0] or "").strip()

        identity_pseudo_to_save = ""
        if identity_mode == "Anonymous":
            identity_pseudo_to_save = ""
        elif identity_mode == "Pseudonym":
            if not pseudo_input:
                msg = "Pseudonym requires a pseudo."
                show_add = "1"
            else:
                identity_pseudo_to_save = pseudo_input
        elif identity_mode == "Identifier":
            if not identifier_pseudo:
                msg = "Identifier requires you to set your identifier pseudo first."
                show_add = "1"
                show_identity = "1"
            else:
                identity_pseudo_to_save = identifier_pseudo
        else:
            identity_mode = "Anonymous"
            identity_pseudo_to_save = ""

        if not title.strip():
            msg = "Title is required."
            show_add = "1"
        elif msg == "":
            insert_event(ev_type, title, description, event_date, event_time, location, identity_mode, identity_pseudo_to_save)
            msg = "Event saved."
            show_add = "0"

    elif post_action == "delete_event":
        eid_raw = (post.get("event_id", [""])[0] or "").strip()
        try:
            eid = int(eid_raw)
        except Exception:
            eid = 0

        if eid > 0:
            delete_event(eid)
            msg = "Event deleted."
        else:
            msg = "Invalid event id."

    elif post_action == "like_event":
        eid_raw = (post.get("event_id", [""])[0] or "").strip()
        try:
            eid = int(eid_raw)
        except Exception:
            eid = 0

        if eid <= 0:
            msg = "Invalid event id."
        else:
            if eid in liked_ids:
                msg = "Already liked (this browser)."
            else:
                like_event(eid)
                liked_ids.add(eid)
                set_cookie_header_value = build_set_cookie(liked_ids)
                msg = "Liked."

rows = search_events(q, type_filter)

# ---------- HTTP headers ----------
print("Content-Type: text/html; charset=utf-8")
if set_cookie_header_value:
    print("Set-Cookie: %s" % set_cookie_header_value)
print("")


# ---------- HTML ----------
print(r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privealy Actuality</title>
<style>
:root{
  --txt:#ffffff;
  --muted:rgba(255,255,255,0.72);
  --muted2:rgba(255,255,255,0.55);
  --card: rgba(255,255,255,0.10);
  --card2: rgba(255,255,255,0.06);
  --line: rgba(255,255,255,0.16);
  --shadow: rgba(0,0,0,0.68);
  --gold: rgba(255,232,180,0.85);
}

*{ box-sizing:border-box; }
html, body{ height:100%; }

body{
  margin:0;
  font-family: Arial, sans-serif;
  color: var(--txt);
  overflow:hidden;
  position: relative;

  background-image:
    radial-gradient(circle at 20% 20%, rgba(255,255,255,0.10), transparent 44%),
    radial-gradient(circle at 80% 30%, rgba(255,255,255,0.07), transparent 52%),
    radial-gradient(circle at 40% 85%, rgba(255,255,255,0.05), transparent 58%),
    linear-gradient(180deg, rgba(0,0,0,0.40), rgba(0,0,0,0.90)),
    url('/fond.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

body::before{
  content:"";
  position: fixed;
  inset:-30px;
  pointer-events:none;
  z-index: 0;
  background:
    radial-gradient(circle at 50% 45%, rgba(255,255,255,0.08), transparent 60%),
    radial-gradient(circle at 50% 55%, rgba(0,0,0,0.00), rgba(0,0,0,0.80) 74%);
}

.stars{
  position: fixed;
  inset: 0;
  pointer-events:none;
  z-index: 0;
  opacity: 0.55;
  background-image:
    radial-gradient(1px 1px at 12% 18%, rgba(255,255,255,0.9), transparent 60%),
    radial-gradient(1px 1px at 28% 62%, rgba(255,255,255,0.7), transparent 60%),
    radial-gradient(1px 1px at 44% 28%, rgba(255,255,255,0.85), transparent 60%),
    radial-gradient(1px 1px at 58% 82%, rgba(255,255,255,0.6), transparent 60%),
    radial-gradient(1px 1px at 74% 64%, rgba(255,255,255,0.75), transparent 60%),
    radial-gradient(1px 1px at 86% 22%, rgba(255,255,255,0.8), transparent 60%),
    radial-gradient(1px 1px at 92% 84%, rgba(255,255,255,0.75), transparent 60%);
  animation: twinkle 4.2s ease-in-out infinite;
}
@keyframes twinkle{
  0%{ opacity: 0.40; transform: translateY(0px); }
  50%{ opacity: 0.70; transform: translateY(-2px); }
  100%{ opacity: 0.40; transform: translateY(0px); }
}

.topbar{
  position: relative;
  z-index: 2;
  width: min(1100px, 94vw);
  margin: 22px auto 0;
  padding: 0 4px;
  display:flex;
  align-items:flex-end;
  justify-content: space-between;
  gap: 14px;
}

.brand{
  margin:0;
  font-size: 30px;
  letter-spacing: 4px;
  text-transform: uppercase;
}

.motto{
  margin-top: 10px;
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--muted);
}

.back_btn_gris{
  display:inline-block;
  width: 58px;
  height: 58px;
  background-image: url('/back_btn_gris.png');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  opacity: 0.88;
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.back_btn_gris:hover{
  transform: scale(1.08);
  opacity: 1;
}

.wrap{
  position: relative;
  z-index: 2;
  width: min(1100px, 94vw);
  margin: 18px auto 28px;
  height: calc(100vh - 120px);
  display:flex;
  flex-direction: column;
  gap: 14px;

  overflow: auto;
  padding-bottom: 24px;
  -webkit-overflow-scrolling: touch;
}

.panel{
  background: linear-gradient(180deg, var(--card), var(--card2));
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 30px 110px var(--shadow);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: 18px;
}

.controls{
  display:flex;
  gap: 12px;
  align-items:center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.search{
  flex: 1;
  min-width: 260px;
  display:flex;
  gap: 10px;
  align-items:center;
}

.search input,
.search select{
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(0,0,0,0.25);
  color: white;
  outline: none;
  font-size: 16px;
  padding: 14px 16px;
}

.search input{
  flex: 1;
  min-width: 220px;
}

.search select{
  width: 190px;
  cursor: pointer;
}

.btn{
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(255,255,255,0.92);
  color: #111;
  border-radius: 999px;
  padding: 12px 16px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
  white-space: nowrap;
}
.btn:hover{
  transform: scale(1.03);
  box-shadow: 0 0 55px rgba(255,232,180,0.16);
}

.btn-ghost{
  background: rgba(0,0,0,0.25);
  color: white;
}

.msg{
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255,232,180,0.22);
  background: rgba(255,232,180,0.10);
  color: rgba(255,255,255,0.92);
}

.grid{
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.form label{
  display:block;
  margin-top: 10px;
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
}

.form input, .form textarea, .form select{
  width:100%;
  margin-top: 6px;
  padding: 12px 12px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(0,0,0,0.25);
  color:white;
  outline:none;
  font-size: 14px;
}

.form textarea{
  min-height: 110px;
  resize: vertical;
}

.list{
  flex: 1;
  overflow:auto;
  padding-right: 4px;
}
.panel.list{ min-height: 0; }

.card{
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(0,0,0,0.22);
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 12px;

  position: relative;
  --accent: rgba(255,232,180,0.26);
}

.card::before{
  content:"";
  position:absolute;
  left:0;
  top:10px;
  bottom:10px;
  width:5px;
  border-radius:999px;
  background: var(--accent);
  box-shadow: 0 0 18px var(--accent);
  opacity: 0.95;
}

.card:hover{
  border-color: var(--accent);
}

.badge{
  display:inline-block;
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  border: 1px solid var(--accent);
  background: rgba(0,0,0,0.18);
  color: rgba(255,255,255,0.92);
}

.t_isee{   --accent: rgba(140,255,235,0.55); }
.t_coming{ --accent: rgba(255,232,180,0.60); }
.t_my{     --accent: rgba(190,120,255,0.55); }

.card-top{
  display:flex;
  gap: 10px;
  align-items:center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.title{
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.5px;
  margin: 10px 0 6px;
}

.meta{
  color: var(--muted2);
  font-size: 12px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.desc{
  color: rgba(255,255,255,0.74);
  font-size: 14px;
  line-height: 1.6;
  margin-top: 10px;
  white-space: pre-wrap;
}

.hr{
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,232,180,0.22), rgba(255,255,255,0.10), rgba(255,232,180,0.22), transparent);
  margin: 16px 0;
}

.small-help{
  color: rgba(255,255,255,0.70);
  line-height: 1.7;
  font-size: 13px;
}

.form-actions{
  position: sticky;
  bottom: 0;
  margin-top: 14px;
  padding-top: 12px;
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  background: linear-gradient(180deg, rgba(0,0,0,0.0), rgba(0,0,0,0.35));
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.mini-form{
  margin:0;
  display:inline-block;
}

.del-btn, .like-btn{
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(0,0,0,0.25);
  color: rgba(255,255,255,0.90);
  border-radius: 999px;
  width: 38px;
  height: 38px;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  display:flex;
  align-items:center;
  justify-content:center;
  transition: transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
  opacity: 0.88;
}

.like-btn{
  width: auto;
  padding: 0 12px;
  gap: 8px;
  font-size: 14px;
  letter-spacing: 1px;
}

.del-btn:hover, .like-btn:hover{
  transform: scale(1.06);
  opacity: 1;
  box-shadow: 0 0 22px rgba(255,255,255,0.12);
}

.like-heart{
  font-size: 18px;
  transform: translateY(-1px);
}

.like-count{
  font-weight: 800;
  font-size: 12px;
  opacity: 0.95;
}

@media (max-width: 980px){
  .grid{ grid-template-columns: 1fr; }
  .search select{ width: 100%; }
}
</style>
</head>
<body>

<div class="stars"></div>

<div class="topbar">
  <div>
    <div style="display:flex; align-items:center; gap:12px;">
      <a href="vrai_index.py" class="back_btn_gris" title="Back"></a>
      <div>
        <h1 class="brand">Privealy Actuality</h1>
        <div class="motto">Signals become events. Events become structure.</div>
      </div>
    </div>
  </div>
</div>
""")

type_opts = [
    ("", "All types"),
    ("I SEE...", "I SEE..."),
    ("COMING...", "COMING..."),
    ("MY EVENT", "MY EVENT"),
]

options_html = []
for val, label in type_opts:
    sel = " selected" if val == type_filter else ""
    options_html.append("<option value=\"%s\"%s>%s</option>" % (esc(val), sel, esc(label)))
options_html = "\n".join(options_html)

print("""
<div class="wrap">

  <div class="panel">
    <div class="controls">
      <form class="search" method="get" action="event.py">
        <input type="text" name="q" value="%s" placeholder="Search an event...">
        <select name="type_filter" title="Filter by type">
          %s
        </select>
        <button class="btn btn-ghost" type="submit">Search</button>
      </form>

      <a href="event.py?identity=1" style="text-decoration:none;">
        <button class="btn btn-ghost" type="button">Identity</button>
      </a>

      <a href="event.py?add=1" style="text-decoration:none;">
        <button class="btn" type="button">Add event</button>
      </a>
    </div>
""" % (esc(q), options_html))

if msg:
    print("<div class='msg'>%s</div>" % esc(msg))

print("</div>")

if show_identity == "1":
    print("""
  <div class="panel">
    <div class="grid">
      <div>
        <div style="font-size:14px; letter-spacing:2px; text-transform:uppercase; color: rgba(255,255,255,0.78);">
          Identity modes
        </div>
        <div class="hr"></div>
        <div class="small-help">
          <div><span class="badge" style="--accent: rgba(255,255,255,0.30);">Anonymous</span> + nothing. No pseudo stored.</div>
          <div style="margin-top:10px;"><span class="badge" style="--accent: rgba(255,255,255,0.30);">Pseudonym</span> + pseudo per event. You can change it every time.</div>
          <div style="margin-top:10px;"><span class="badge" style="--accent: rgba(255,255,255,0.30);">Identifier</span> + your unique pseudo. Locked: same for all Identifier events.</div>
        </div>
      </div>

      <div>
        <form class="form" method="post" action="event.py?identity=1">
          <input type="hidden" name="post_action" value="save_identifier">
          <label>Your Identifier pseudo (global)</label>
          <input type="text" name="identifier_pseudo" value="%s" placeholder="Ex: Wild / Oracle / etc.">
          <div class="form-actions">
            <button class="btn" type="submit">Save</button>
            <a href="event.py" style="text-decoration:none;">
              <button class="btn btn-ghost" type="button">Close</button>
            </a>
          </div>
        </form>
      </div>
    </div>
  </div>
""" % esc(identifier_pseudo))

if show_add == "1":
    print("""
  <div class="panel">
    <div class="grid">
      <div>
        <div style="font-size:14px; letter-spacing:2px; text-transform:uppercase; color: rgba(255,255,255,0.78);">
          Record an event
        </div>
        <div class="hr"></div>

        <div style="font-size:12px; letter-spacing:2px; text-transform:uppercase; color: rgba(255,232,180,0.85);">
          Types
        </div>
        <div style="margin-top:10px; color: rgba(255,255,255,0.70); line-height:1.7;">
          <div><span class="badge t_isee">I SEE...</span> Observation / perception.</div>
          <div style="margin-top:8px;"><span class="badge t_coming">COMING...</span> Future event.</div>
          <div style="margin-top:8px;"><span class="badge t_my">MY EVENT</span> Personal event.</div>
        </div>

        <div class="hr"></div>

        <div style="font-size:12px; letter-spacing:2px; text-transform:uppercase; color: rgba(255,232,180,0.85);">
          Identity modes (what it implies)
        </div>
        <div class="small-help" style="margin-top:10px;">
          <div><span class="badge" style="--accent: rgba(255,255,255,0.30);">Anonymous</span> + nothing (no pseudo stored).</div>
          <div style="margin-top:8px;"><span class="badge" style="--accent: rgba(255,255,255,0.30);">Pseudonym</span> + pseudo per event (you can change each time).</div>
          <div style="margin-top:8px;"><span class="badge" style="--accent: rgba(255,255,255,0.30);">Identifier</span> + your global pseudo (locked).</div>
          <div style="margin-top:10px; color: rgba(255,255,255,0.65);">
            Current Identifier: <b>%s</b>
          </div>
        </div>
      </div>

      <div>
        <form class="form" method="post" action="event.py?add=1">
          <input type="hidden" name="post_action" value="save_event">

          <label>Type</label>
          <select name="type">
            <option value="I SEE...">I SEE...</option>
            <option value="COMING...">COMING...</option>
            <option value="MY EVENT">MY EVENT</option>
          </select>

          <label>Identity mode</label>
          <select name="identity_mode">
            <option value="Anonymous">Anonymous</option>
            <option value="Pseudonym">Pseudonym</option>
            <option value="Identifier">Identifier</option>
          </select>

          <label>Pseudo (only for Pseudonym)</label>
          <input type="text" name="identity_pseudo" placeholder="Ex: Raven / Observer / etc.">

          <label>Title (required)</label>
          <input type="text" name="title" placeholder="Short title">

          <label>Description</label>
          <textarea name="description" placeholder="What happened? What is coming?"></textarea>

          <div class="grid" style="margin-top:6px;">
            <div>
              <label>Date</label>
              <input type="date" name="event_date">
            </div>
            <div>
              <label>Time (optional)</label>
              <input type="time" name="event_time">
            </div>
          </div>

          <label>Location</label>
          <input type="text" name="location" placeholder="Place / city / room">

          <div class="form-actions">
            <button class="btn" type="submit">Save</button>
            <a href="event.py" style="text-decoration:none;">
              <button class="btn btn-ghost" type="button">Close</button>
            </a>
            <a href="event.py?identity=1" style="text-decoration:none;">
              <button class="btn btn-ghost" type="button">Set Identifier</button>
            </a>
          </div>
        </form>
      </div>
    </div>
  </div>
""" % esc(identifier_pseudo if identifier_pseudo else "not set"))

print("""
  <div class="panel list">
""")

if not rows:
    print("<div style='color: rgba(255,255,255,0.70);'>No events yet.</div>")
else:
    for (eid, ev_type, title, description, event_date, event_time, location, created_at, identity_mode, identity_pseudo_display, likes) in rows:
        t = (ev_type or "").strip().upper()
        type_class = "t_isee"
        if t == "COMING...":
            type_class = "t_coming"
        elif t == "MY EVENT":
            type_class = "t_my"

        im = (identity_mode or "Anonymous").strip()
        ip = (identity_pseudo_display or "").strip()

        if im == "Identifier":
            identity_label = "Identifier" + (" + " + ip if ip else "")
        elif im == "Pseudonym":
            identity_label = "Pseudonym" + (" + " + ip if ip else "")
        else:
            identity_label = "Anonymous"

        meta_parts = []
        if event_date:
            meta_parts.append(event_date + (" " + event_time if event_time else ""))
        if location:
            meta_parts.append(location)
        meta_parts.append(identity_label)
        meta_parts.append("logged %s" % created_at)
        meta = " | ".join([esc(x) for x in meta_parts if x])

        try:
            likes_int = int(likes or 0)
        except Exception:
            likes_int = 0

        liked_here = (int(eid) in liked_ids)
        like_title = "Liked already" if liked_here else "Like"
        like_opacity = "0.55" if liked_here else "0.88"
        like_disabled = "disabled" if liked_here else ""

        print("""
    <div class="card %s">
      <div class="card-top">
        <span class="badge %s">%s</span>

        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; justify-content:flex-end;">
          <div class="meta">%s</div>

          <form class="mini-form" method="post" action="event.py" title="%s">
            <input type="hidden" name="post_action" value="like_event">
            <input type="hidden" name="event_id" value="%d">
            <button class="like-btn" type="submit" style="opacity:%s;" %s>
              <span class="like-heart">❤</span>
              <span class="like-count">%d</span>
            </button>
          </form>

          <form class="mini-form" method="post" action="event.py" onsubmit="return confirm('Delete this event?');">
            <input type="hidden" name="post_action" value="delete_event">
            <input type="hidden" name="event_id" value="%d">
            <button class="del-btn" type="submit" title="Delete">×</button>
          </form>
        </div>
      </div>

      <div class="title">%s</div>
""" % (
            type_class,
            type_class,
            esc(ev_type),
            meta,
            esc(like_title),
            int(eid),
            like_opacity,
            like_disabled,
            likes_int,
            int(eid),
            esc(title),
        ))

        if description:
            print("<div class='desc'>%s</div>" % esc(description))
        else:
            print("<div class='desc' style='opacity:0.7;'>No description.</div>")

        print("</div>")

print("""
  </div>

</div>
</body>
</html>
""")