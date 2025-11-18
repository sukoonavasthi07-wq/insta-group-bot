"""
app.py — Instagram DM sender (single-account, production mode)

Features:
- Single Instagram account configured in UI (username + password)
- sessions/session.json automatically created and reused
- Send DMs to usernames (individuals) or group thread IDs (numeric)
- Cyclone delay pattern + jitter, min/max delays
- Start / Stop works reliably (background worker + stop Event)
- Live logs streamed to the dashboard via Server-Sent Events (SSE)
- Test Mode toggle (simulate sends) and a required "I accept responsibility" consent checkbox to enable real sends
- Rate limiter (max messages per hour) to help avoid abuse
- Retries with exponential backoff
- Start command: python app.py
Security:
- Credentials kept in memory only (not written to disk). Session tokens saved to sessions/session.json.
- Do NOT commit sessions/session.json to source control.
- Use this responsibly (no spam).
"""

import os
import time
import json
import random
import threading
import traceback
from datetime import datetime, timedelta
from io import TextIOWrapper
from typing import List

from flask import (
    Flask, render_template_string, request, redirect, url_for,
    Response, stream_with_context, send_from_directory, jsonify, flash
)

# instagrapi for real Instagram actions
try:
    from instagrapi import Client
except Exception:
    Client = None

# --------- Paths / setup ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(APP_DIR, "sessions")
LOGS_DIR = os.path.join(APP_DIR, "logs")
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

SESSION_FILE = os.path.join(SESSIONS_DIR, "session.json")
LOG_FILE = os.path.join(LOGS_DIR, "live.log")
MSG_FILE_TMP = os.path.join(APP_DIR, "messages.txt")

# --------- Flask ----------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "change_me_secret_for_prod")

# --------- Runtime state ----------
worker_thread = None
worker_stop_event = threading.Event()
worker_lock = threading.Lock()
worker_running = False

# credentials (in-memory only)
account_credentials = {"username": None, "password": None}

# messages & config
messages: List[str] = []
config = {
    "targets": [],  # usernames
    "group_ids": [],  # thread ids (strings)
    "min_delay": 3.0,
    "max_delay": 6.0,
    "cyclone_pattern": [2.0, 5.0, 10.0, 4.0],
    "cyclone_jitter": 0.25,
    "max_retries": 4,
    "base_backoff": 2.0,
    "max_per_hour": 200,  # basic rate-limit default
}

# in-memory send timestamps for rate limiting (list of datetimes)
send_timestamps: List[datetime] = []

# log buffer (SSE)
log_lines = []
LOG_BUFFER_MAX = 2000
log_condition = threading.Condition()


def now_ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def append_log(line: str):
    full = f"[{now_ts()}] {line}"
    # append to logfile
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full + "\n")
    except Exception:
        pass
    # buffer + notify
    with log_condition:
        log_lines.append(full)
        if len(log_lines) > LOG_BUFFER_MAX:
            del log_lines[0: len(log_lines)-LOG_BUFFER_MAX]
        log_condition.notify_all()
    print(full)


# --------- Session / Client management ----------
def ensure_client(username: str, password: str):
    """
    Return a logged-in Client (instagrapi). Persists session to SESSION_FILE.
    Raises RuntimeError on failure.
    """
    if Client is None:
        raise RuntimeError("instagrapi not installed. Add it to requirements.txt")
    cl = Client()
    # try to reuse session
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            # instagrapi may reuse session; call login to ensure validity
            cl.login(username, password)
            cl.dump_settings(SESSION_FILE)
            append_log(f"Reused session for {username}")
            return cl
        except Exception as e:
            append_log(f"Could not reuse session: {e}; will attempt fresh login")

    # fresh login
    append_log(f"Logging in as {username} (this may trigger 2FA/challenge)...")
    cl = Client()
    cl.login(username, password)  # may raise exceptions for 2FA/challenge
    try:
        cl.dump_settings(SESSION_FILE)
    except Exception:
        append_log("Warning: could not save session file")
    append_log(f"Logged in and session saved for {username}")
    return cl


# --------- Rate limiting helpers ----------
def allowed_by_rate_limit() -> bool:
    """Return True if sending another message is allowed under max_per_hour."""
    now = datetime.utcnow()
    window_start = now - timedelta(hours=1)
    # prune old timestamps
    while send_timestamps and send_timestamps[0] < window_start:
        send_timestamps.pop(0)
    return len(send_timestamps) < int(config.get("max_per_hour", 200))


def record_send_timestamp():
    send_timestamps.append(datetime.utcnow())


# --------- Delay/backoff helpers ----------
def cyclone_delay(index: int) -> float:
    pattern = config.get("cyclone_pattern") or []
    jitter_frac = float(config.get("cyclone_jitter", 0.25) or 0.25)
    if not pattern:
        base = random.uniform(config.get("min_delay", 3.0), config.get("max_delay", 6.0))
    else:
        base = float(pattern[index % len(pattern)])
    jitter = jitter_frac * base
    delay = base + random.uniform(-jitter, jitter)
    return max(0.2, delay)


def exponential_backoff(attempt: int) -> float:
    base = float(config.get("base_backoff", 2.0))
    backoff = base * (2 ** (attempt - 1))
    backoff += random.uniform(0, backoff * 0.25)
    return backoff


# --------- Send helpers ----------
def send_text_with_retries(client, username: str, message: str) -> bool:
    """Send DM to username (by resolving to user_id). Returns True on success."""
    attempt = 0
    max_retries = int(config.get("max_retries", 4))
    while attempt < max_retries:
        attempt += 1
        try:
            user_id = client.user_id_from_username(username)
            # instagrapi convenient syntax: client.direct_send(text, [user_id])
            client.direct_send(message, [user_id])
            append_log(f"Sent to @{username}")
            return True
        except Exception as e:
            append_log(f"Send attempt {attempt} to @{username} failed: {e}")
            if attempt >= max_retries:
                append_log(f"Giving up on @{username}")
                return False
            backoff = exponential_backoff(attempt)
            append_log(f"Retrying after {backoff:.1f}s")
            time.sleep(backoff)
    return False


def send_text_to_thread_with_retries(client, thread_id: str, message: str) -> bool:
    """Send message to group thread id (numeric)."""
    attempt = 0
    max_retries = int(config.get("max_retries", 4))
    while attempt < max_retries:
        attempt += 1
        try:
            client.direct_send(message, thread_ids=[int(thread_id)])
            append_log(f"Sent to thread {thread_id}")
            return True
        except Exception as e:
            append_log(f"Thread send attempt {attempt} to {thread_id} failed: {e}")
            if attempt >= max_retries:
                append_log(f"Giving up on thread {thread_id}")
                return False
            backoff = exponential_backoff(attempt)
            append_log(f"Retrying after {backoff:.1f}s")
            time.sleep(backoff)
    return False


# --------- Background worker ----------
def worker_loop(username: str, password: str, test_mode: bool, consent_checked: bool):
    global worker_running
    append_log("Worker starting (REAL mode)" if not test_mode else "Worker starting (TEST mode - no real sends)")
    try:
        client = None
        if not test_mode:
            try:
                client = ensure_client(username, password)
            except Exception as e:
                append_log(f"Login error: {e}")
                with worker_lock:
                    worker_running = False
                return
    except Exception:
        append_log("Fatal error preparing client")
        with worker_lock:
            worker_running = False
        return

    index = 0
    send_count = 0

    while not worker_stop_event.is_set():
        # assemble targets
        targets = []
        targets.extend(config.get("targets", []))
        targets.extend(config.get("group_ids", []))
        if not targets:
            append_log("No targets configured; worker sleeping 5s")
            for _ in range(5):
                if worker_stop_event.is_set():
                    break
                time.sleep(1)
            continue
        if not messages:
            append_log("No messages loaded; worker sleeping 5s")
            for _ in range(5):
                if worker_stop_event.is_set():
                    break
                time.sleep(1)
            continue

        for t in targets:
            if worker_stop_event.is_set():
                break

            # enforce rate limit
            if not test_mode and not allowed_by_rate_limit():
                append_log("Rate limit reached (per-hour). Sleeping 30s before re-check.")
                for _ in range(6):
                    if worker_stop_event.is_set():
                        break
                    time.sleep(5)
                continue

            # choose message
            msg = messages[index % len(messages)]
            index += 1
            # placeholder substitution
            if "{name}" in msg and account_credentials.get("username"):
                send_msg = msg.replace("{name}", account_credentials.get("username"))
            else:
                send_msg = msg

            append_log(f"Preparing to send to {t}: {send_msg[:80]!r}")

            if test_mode or not consent_checked:
                # simulated send
                try:
                    # simulate small send delay
                    time.sleep(random.uniform(0.4, 1.1))
                    append_log(f"(TEST) Sent to {t}")
                    if not test_mode:
                        # this code path is only when consent unchecked but real mode — but we always simulate
                        pass
                    record_send_timestamp()
                except Exception as e:
                    append_log(f"(TEST) Simulated send error to {t}: {e}")
            else:
                # real send path
                try:
                    if str(t).isdigit():
                        ok = send_text_to_thread_with_retries(client, t, send_msg)
                    else:
                        ok = send_text_with_retries(client, t, send_msg)
                    if ok:
                        record_send_timestamp()
                    else:
                        append_log(f"Failed to send to {t}")
                except Exception as e:
                    append_log(f"Unexpected send error to {t}: {e}\n{traceback.format_exc()}")

            # save session after each send (best effort)
            if client:
                try:
                    client.dump_settings(SESSION_FILE)
                except Exception:
                    pass

            # apply cyclone delay
            d = cyclone_delay(send_count)
            send_count += 1
            append_log(f"Delay applied: {d:.2f}s")
            slept = 0.0
            while slept < d and not worker_stop_event.is_set():
                time.sleep(min(0.5, d - slept))
                slept += min(0.5, d - slept)

    append_log("Worker stopping")
    with worker_lock:
        worker_running = False


# --------- Dashboard UI (Bootstrap) & SSE ----------
DASH_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Instagram DM Sender</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body{background:#f6f8fb;padding:20px}
    .logbox{background:#061226;color:#dff7ff;padding:12px;height:360px;overflow:auto;font-family:monospace;border-radius:8px}
    .btn-start{background:linear-gradient(90deg,#0ea5e9,#0b79f7);color:#fff;font-weight:700}
    .btn-stop{background:linear-gradient(90deg,#ef4444,#dc2626);color:#fff;font-weight:700}
  </style>
</head>
<body>
<div class="container">
  <h3 class="mb-3">Instagram DM Sender (Single Account)</h3>

  <div class="card mb-3 p-3">
    <form method="post" action="/save_account">
      <div class="row g-2">
        <div class="col-md-5"><input name="username" class="form-control" placeholder="Instagram username" value="{{ username or '' }}" required></div>
        <div class="col-md-5"><input name="password" type="password" class="form-control" placeholder="Instagram password" value="" required></div>
        <div class="col-md-2"><button class="btn btn-outline-primary w-100">Save</button></div>
      </div>
      <div class="small mt-2 text-muted">Credentials stored in memory only; session saved to sessions/session.json after login.</div>
    </form>
  </div>

  <div class="row g-4">
    <div class="col-lg-7">
      <div class="card p-3 mb-3">
        <form method="post" action="/upload_messages" enctype="multipart/form-data">
          <label class="form-label">Messages (one per line) — use {name} placeholder</label>
          <textarea name="messages_text" class="form-control mb-2" rows="5">{{ messages_text }}</textarea>
          <label class="form-label">Or upload messages.txt</label>
          <input type="file" name="messages_file" class="form-control mb-2" accept=".txt">
          <button class="btn btn-secondary">Save messages</button>
        </form>
      </div>

      <div class="card p-3 mb-3">
        <form method="post" action="/save_config">
          <label class="form-label">Targets (usernames, comma-separated)</label>
          <input name="targets" class="form-control mb-2" value="{{ targets }}">
          <label class="form-label">Group thread IDs (comma-separated)</label>
          <input name="group_ids" class="form-control mb-2" value="{{ group_ids }}">
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label">Min delay (s)</label><input name="min_delay" class="form-control" value="{{ min_delay }}"></div>
            <div class="col-md-3"><label class="form-label">Max delay (s)</label><input name="max_delay" class="form-control" value="{{ max_delay }}"></div>
            <div class="col-md-6"><label class="form-label">Cyclone pattern (comma-separated)</label><input name="cyclone_pattern" class="form-control" value="{{ cyclone_pattern }}"></div>
          </div>
          <div class="row g-2 mt-2">
            <div class="col-md-4"><label class="form-label">Cyclone jitter</label><input name="cyclone_jitter" class="form-control" value="{{ cyclone_jitter }}"></div>
            <div class="col-md-4"><label class="form-label">Max per hour</label><input name="max_per_hour" class="form-control" value="{{ max_per_hour }}"></div>
            <div class="col-md-4"><label class="form-label">Test mode</label><select name="test_mode" class="form-select"><option value="1">Enabled (simulate)</option><option value="0">Disabled (real sends)</option></select></div>
          </div>
          <div class="form-check mt-2">
            <input class="form-check-input" type="checkbox" id="consent" name="consent">
            <label class="form-check-label small" for="consent">I confirm recipients have consented and I accept responsibility for using the bot.</label>
          </div>
          <div class="mt-2"><button class="btn btn-secondary">Save config</button></div>
        </form>
      </div>

      <div class="d-flex gap-2 mb-3">
        <form method="post" action="/start"><button class="btn-start btn px-4">🔵 START BOT</button></form>
        <form method="post" action="/stop"><button class="btn-stop btn px-4">🔴 STOP BOT</button></form>
        <div class="align-self-center ms-3">Status: <strong id="status">{{ status }}</strong></div>
      </div>

    </div>

    <div class="col-lg-5">
      <div class="card p-3 mb-3">
        <h6>Live logs</h6>
        <div id="logbox" class="logbox"></div>
        <div class="mt-2"><a class="btn btn-sm btn-outline-secondary" href="/download_log">Download full log</a></div>
      </div>

      <div class="card p-3">
        <h6>Notes</h6>
        <ul class="small">
          <li>Test mode simulates sends; disable to send real messages (requires consent checkbox).</li>
          <li>If Instagram challenges login (2FA/checkpoint), you'll see log instructions — manual resolution may be required.</li>
          <li>Session tokens saved to <code>sessions/session.json</code>.</li>
        </ul>
      </div>
    </div>
  </div>
</div>

<script>
  // SSE
  const src = new EventSource('/stream');
  const box = document.getElementById('logbox');
  src.onmessage = function(e){
    box.innerText = (box.innerText ? box.innerText + "\\n" : "") + e.data;
    box.scrollTop = box.scrollHeight;
  };
  async function updateStatus(){
    const r = await fetch('/status'); const j = await r.json();
    document.getElementById('status').innerText = j.running ? 'running' : 'stopped';
  }
  setInterval(updateStatus, 2500);
  updateStatus();
</script>

</body></html>
"""

# --------- Flask routes ----------
@app.route("/")
def index():
    msgs_text = "\n".join(messages)
    return render_template_string(
        DASH_HTML,
        username=account_credentials.get("username"),
        messages_text=msgs_text,
        targets=",".join(config.get("targets", [])),
        group_ids=",".join(config.get("group_ids", [])),
        min_delay=config.get("min_delay"),
        max_delay=config.get("max_delay"),
        cyclone_pattern=",".join(str(x) for x in config.get("cyclone_pattern", [])),
        cyclone_jitter=config.get("cyclone_jitter"),
        max_per_hour=config.get("max_per_hour"),
        status="running" if worker_running else "stopped",
    )


@app.route("/save_account", methods=["POST"])
def save_account():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not username or not password:
        append_log("Account save failed: username & password required")
        return redirect(url_for("index"))
    account_credentials["username"] = username
    account_credentials["password"] = password
    append_log("Account credentials saved in memory")
    # attempt to create session (best-effort)
    if Client is not None:
        try:
            ensure_client(username, password)
        except Exception as e:
            append_log(f"Session creation warning: {e}")
    else:
        append_log("instagrapi not installed — real sends will fail until installed")
    return redirect(url_for("index"))


@app.route("/upload_messages", methods=["POST"])
def upload_messages():
    global messages
    text = request.form.get("messages_text", "").strip()
    f = request.files.get("messages_file")
    if f and f.filename and f.filename.lower().endswith(".txt"):
        stream = TextIOWrapper(f.stream, encoding="utf-8", errors="ignore")
        messages = [ln.rstrip("\n") for ln in stream if ln.strip()]
        append_log(f"Uploaded messages.txt ({len(messages)} lines)")
        # also write tmp file
        with open(MSG_FILE_TMP, "w", encoding="utf-8") as ff:
            for m in messages:
                ff.write(m + "\n")
    else:
        messages = [ln for ln in text.splitlines() if ln.strip()]
        append_log(f"Saved messages from textarea ({len(messages)} lines)")
        with open(MSG_FILE_TMP, "w", encoding="utf-8") as ff:
            for m in messages:
                ff.write(m + "\n")
    return redirect(url_for("index"))


@app.route("/download_messages")
def download_messages():
    if not os.path.exists(MSG_FILE_TMP):
        open(MSG_FILE_TMP, "a").close()
    return send_from_directory(APP_DIR, "messages.txt", as_attachment=True)


@app.route("/save_config", methods=["POST"])
def save_config():
    config["targets"] = [t.strip() for t in request.form.get("targets", "").split(",") if t.strip()]
    config["group_ids"] = [g.strip() for g in request.form.get("group_ids", "").split(",") if g.strip()]
    try:
        config["min_delay"] = float(request.form.get("min_delay", config.get("min_delay", 3.0)))
        config["max_delay"] = float(request.form.get("max_delay", config.get("max_delay", 6.0)))
    except Exception:
        pass
    try:
        config["cyclone_pattern"] = [float(x) for x in request.form.get("cyclone_pattern", ",".join(str(x) for x in config.get("cyclone_pattern", []))).split(",") if x.strip()]
    except Exception:
        pass
    try:
        config["cyclone_jitter"] = float(request.form.get("cyclone_jitter", config.get("cyclone_jitter", 0.25)))
    except Exception:
        pass
    try:
        config["max_per_hour"] = int(request.form.get("max_per_hour", config.get("max_per_hour", 200)))
    except Exception:
        pass
    # test_mode & consent saved but applied only on /start
    append_log("Config saved")
    return redirect(url_for("index"))


@app.route("/start", methods=["POST"])
def start():
    global worker_thread, worker_running, worker_stop_event
    with worker_lock:
        if worker_running:
            append_log("Start requested but already running")
            return redirect(url_for("index"))
        username = account_credentials.get("username")
        password = account_credentials.get("password")
        if not username or not password:
            append_log("Start failed: account not configured")
            return redirect(url_for("index"))
        # get test_mode and consent from form submission? the Save Config form sets them; allow start to read fields optionally
        # For safety: read latest posted fields from request.form if present
        test_mode = request.form.get("test_mode")
        consent_flag = request.form.get("consent")
        # fallback to safe defaults: if test_mode not provided, default to simulate
        test_mode_bool = True if test_mode is None else (str(test_mode) == "1" or str(test_mode).lower() in ("true","1"))
        consent_checked = True if consent_flag and (consent_flag.lower() in ("on","1","true")) else False
        # If real sends requested (test_mode disabled) require consent
        if not test_mode_bool and not consent_checked:
            append_log("Start blocked: real sends require consent checkbox checked")
            return redirect(url_for("index"))

        worker_stop_event.clear()
        worker_thread = threading.Thread(target=worker_loop, args=(username, password, test_mode_bool, consent_checked), daemon=True)
        worker_thread.start()
        worker_running = True
        append_log(f"Worker launched (test_mode={test_mode_bool}, consent={consent_checked})")
        return redirect(url_for("index"))


@app.route("/stop", methods=["POST"])
def stop():
    global worker_stop_event
    if not worker_running:
        append_log("Stop requested but worker not running")
        return redirect(url_for("index"))
    worker_stop_event.set()
    append_log("Stop requested — stop signal sent")
    return redirect(url_for("index"))


@app.route("/status")
def status():
    return jsonify({"running": worker_running})


@app.route("/download_log")
def download_log():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, "a").close()
    return send_from_directory(LOGS_DIR, os.path.basename(LOG_FILE), as_attachment=True)


@app.route("/stream")
def stream():
    def event_stream():
        # send last 200 lines first
        with log_condition:
            last = list(log_lines[-200:])
        for l in last:
            yield f"data: {l}\n\n"
        idx = len(last)
        while True:
            with log_condition:
                log_condition.wait(timeout=10)
                new = log_lines[idx:]
            if new:
                for l in new:
                    yield f"data: {l}\n\n"
                idx += len(new)
            else:
                yield ": keep-alive\n\n"
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")


# --------- Startup ----------
if __name__ == "__main__":
    append_log("App starting up (production-capable)")
    if Client is None:
        append_log("WARNING: instagrapi is not installed. Install it to enable real sends.")
    # ensure log file exists
    open(LOG_FILE, "a").close()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
