# app.py - Instagram DM Bot (single account, session.json, stable Start/Stop, attractive Bootstrap UI)
"""
Single-user Instagram DM sender web UI for Render.
- Single Instagram account (username + password) configured via UI
- session.json is automatically created and reused (sessions/session.json)
- Start / Stop works reliably (background worker thread)
- Attractive UI using Bootstrap 5 (served from CDN)
- Live logs streamed to browser using Server-Sent Events (SSE)
- Configuration: messages (textarea or upload), targets (usernames or group thread ids), delays, cyclone pattern + jitter
- Start command: python app.py

SECURITY NOTE: This app stores the Instagram password in memory for the running process and stores session.json file. Do NOT commit your session.json to source control.
"""

import os
import time
import json
import random
import threading
import queue
import traceback
from datetime import datetime
from io import TextIOWrapper

from flask import (
    Flask, render_template_string, request, redirect, url_for, send_from_directory,
    Response, stream_with_context, jsonify
)

try:
    from instagrapi import Client
except Exception:
    Client = None

# -------------------------
# Configuration / Paths
# -------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(APP_DIR, "sessions")
LOGS_DIR = os.path.join(APP_DIR, "logs")
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

SESSION_FILE = os.path.join(SESSIONS_DIR, "session.json")
LOG_FILE = os.path.join(LOGS_DIR, "live.log")

# -------------------------
# Flask app
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', 'change_this_secret')

# -------------------------
# Runtime state
# -------------------------
worker_thread = None
worker_stop_event = threading.Event()
worker_lock = threading.Lock()
worker_running = False

# Store current account credentials in memory (single account)
account_credentials = {"username": None, "password": None}

# Messages and config
messages = []
config = {
    "targets": [],         # list of usernames (strings)
    "group_ids": [],       # list of thread ids (strings)
    "min_delay": 3.0,
    "max_delay": 6.0,
    "cyclone_pattern": [2.0, 5.0, 10.0, 4.0],
    "cyclone_jitter": 0.25,
}

# Simple in-memory log broadcaster
log_condition = threading.Condition()
log_lines = []          # circular buffer of recent lines
LOG_BUFFER_SIZE = 1000


def _now_ts():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')


def append_log(line: str):
    full = f"[{_now_ts()}] {line}"
    # write to file
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(full + "
")
    except Exception:
        pass
    # keep circular buffer
    with log_condition:
        log_lines.append(full)
        if len(log_lines) > LOG_BUFFER_SIZE:
            del log_lines[0: len(log_lines) - LOG_BUFFER_SIZE]
        log_condition.notify_all()
    print(full)


# -------------------------
# Session management
# -------------------------

def ensure_client(username: str, password: str):
    """Return a logged-in instagrapi Client. Creates/loads SESSION_FILE."""
    if Client is None:
        raise RuntimeError('instagrapi not installed; add it to requirements.txt')

    cl = Client()
    # Try to reuse session file
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            # try a quick login (instagrapi will reuse session when valid)
            cl.login(username, password)
            cl.dump_settings(SESSION_FILE)
            append_log(f'Reused session for {username}')
            return cl
        except Exception as e:
            append_log(f'Could not reuse session: {e}; will attempt fresh login')

    # fresh login
    append_log(f'Logging in as {username} (this may require 2FA or challenge)')
    cl = Client()
    cl.login(username, password)
    try:
        cl.dump_settings(SESSION_FILE)
    except Exception:
        append_log('Warning: unable to save session file')
    append_log(f'Logged in: {username} (session saved)')
    return cl


# -------------------------
# Sending helpers
# -------------------------

def cyclone_delay(index: int) -> float:
    pattern = config.get('cyclone_pattern') or []
    jitter_frac = float(config.get('cyclone_jitter', 0.25) or 0.25)
    if not pattern:
        base = random.uniform(config.get('min_delay', 3.0), config.get('max_delay', 6.0))
    else:
        base = float(pattern[index % len(pattern)])
    jitter = jitter_frac * base
    delay = base + random.uniform(-jitter, jitter)
    return max(0.2, delay)


def exponential_backoff(attempt: int) -> float:
    base = 2.0
    backoff = base * (2 ** (attempt - 1))
    backoff += random.uniform(0, backoff * 0.25)
    return backoff


def send_message_via_client(cl, target: str, message: str) -> bool:
    """Send message to target (username or numeric thread id). Returns True on success."""
    try:
        # If purely digits, treat as thread id
        if str(target).isdigit():
            cl.direct_send(message, thread_ids=[int(target)])
            append_log(f"Sent to thread {target}")
            return True
        else:
            user_id = cl.user_id_from_username(target)
            # instagrapi supports direct_send(text, [user_id])
            cl.direct_send(message, [user_id])
            append_log(f"Sent to @{target}")
            return True
    except Exception as e:
        append_log(f"Send error to {target}: {e}")
        return False


# -------------------------
# Background worker
# -------------------------

def worker_loop(username, password):
    global worker_running
    append_log('Worker starting...')
    try:
        cl = ensure_client(username, password)
    except Exception as e:
        append_log(f'Login failed: {e}')
        with worker_lock:
            worker_running = False
        return

    index = 0
    while not worker_stop_event.is_set():
        # Build list of all targets to send in one pass
        targets = []
        targets.extend(config.get('targets', []))
        targets.extend(config.get('group_ids', []))

        if not targets:
            append_log('No targets configured; worker sleeping 5s')
            # Sleep responsive to stop_event
            for _ in range(5):
                if worker_stop_event.is_set():
                    break
                time.sleep(1)
            continue

        for t in targets:
            if worker_stop_event.is_set():
                break
            # pick message
            if not messages:
                append_log('No messages loaded; skipping')
                break
            msg = messages[index % len(messages)]
            index += 1
            # substitute {name} with username if present
            if '{name}' in msg and account_credentials.get('username'):
                send_msg = msg.replace('{name}', account_credentials.get('username'))
            else:
                send_msg = msg

            # Send with retries
            success = False
            attempt = 0
            while attempt < 4 and not success:
                attempt += 1
                try:
                    ok = send_message_via_client(cl, t, send_msg)
                    if ok:
                        success = True
                        break
                except Exception as e:
                    append_log(f'Error on send attempt {attempt}: {e}')
                if not success:
                    backoff = exponential_backoff(attempt)
                    append_log(f'Retrying after {backoff:.1f}s')
                    # responsive sleep
                    slept = 0.0
                    while slept < backoff and not worker_stop_event.is_set():
                        time.sleep(0.5)
                        slept += 0.5

            # Save session after each send to keep cookies fresh
            try:
                cl.dump_settings(SESSION_FILE)
            except Exception:
                pass

            # Apply cyclone delay
            d = cyclone_delay(index)
            append_log(f'Delay applied: {d:.2f}s')
            slept = 0.0
            while slept < d and not worker_stop_event.is_set():
                time.sleep(min(0.5, d - slept))
                slept += 0.5

    append_log('Worker loop exiting')
    with worker_lock:
        worker_running = False


# -------------------------
# Flask routes
# -------------------------

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Instagram DM Bot — Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      body { padding: 20px; background: #f6f8fb; }
      .log-box { background: #0b1220; color: #d6f3ff; padding: 12px; height: 360px; overflow:auto; font-family: monospace; }
      .btn-start { background: #0d6efd; color: white; }
      .btn-stop { background: #dc3545; color: white; }
    </style>
  </head>
  <body>
    <div class="container">
      <h2 class="mb-3">Instagram DM Bot — Dashboard</h2>

      <div class="card mb-3">
        <div class="card-body">
          <h5 class="card-title">Account (single)</h5>
          <form method="post" action="/save_account">
            <div class="row">
              <div class="col-md-5 mb-2">
                <input name="username" class="form-control" placeholder="Instagram username" value="{{ username or '' }}" required>
              </div>
              <div class="col-md-5 mb-2">
                <input name="password" type="password" class="form-control" placeholder="Instagram password" value="" required>
              </div>
              <div class="col-md-2 mb-2">
                <button class="btn btn-primary w-100" type="submit">Save</button>
              </div>
            </div>
          </form>
          <div class="small mt-2 text-muted">session.json will be created automatically after successful login.</div>
        </div>
      </div>

      <div class="card mb-3">
        <div class="card-body">
          <h5 class="card-title">Messages</h5>
          <form method="post" action="/upload_messages" enctype="multipart/form-data">
            <div class="mb-2">
              <textarea name="messages_text" class="form-control" rows="4" placeholder="One message per line">{{ messages_text }}</textarea>
            </div>
            <div class="mb-2">
              <input type="file" name="messages_file" accept=".txt" class="form-control">
            </div>
            <button class="btn btn-secondary" type="submit">Save messages</button>
          </form>
        </div>
      </div>

      <div class="card mb-3">
        <div class="card-body">
          <h5 class="card-title">Targets & Delays</h5>
          <form method="post" action="/save_config">
            <div class="mb-2">
              <label class="form-label">Targets (comma-separated usernames)</label>
              <input name="targets" class="form-control" value="{{ targets }}" placeholder="user1,user2">
            </div>
            <div class="mb-2">
              <label class="form-label">Group thread IDs (comma-separated)</label>
              <input name="group_ids" class="form-control" value="{{ group_ids }}" placeholder="1234567890,11223344">
            </div>

            <div class="row">
              <div class="col-md-3 mb-2">
                <label class="form-label">Min Delay (s)</label>
                <input name="min_delay" class="form-control" value="{{ min_delay }}">
              </div>
              <div class="col-md-3 mb-2">
                <label class="form-label">Max Delay (s)</label>
                <input name="max_delay" class="form-control" value="{{ max_delay }}">
              </div>
              <div class="col-md-6 mb-2">
                <label class="form-label">Cyclone pattern (comma-separated)</label>
                <input name="cyclone_pattern" class="form-control" value="{{ cyclone_pattern }}">
              </div>
            </div>

            <div class="mb-2">
              <label class="form-label">Cyclone jitter (fraction, e.g. 0.25)</label>
              <input name="cyclone_jitter" class="form-control" value="{{ cyclone_jitter }}">
            </div>

            <button class="btn btn-secondary" type="submit">Save config</button>
          </form>
        </div>
      </div>

      <div class="mb-3 d-flex gap-2">
        <form method="post" action="/start" style="display:inline">
          <button class="btn btn-start btn-start-lg" type="submit">🔵 START BOT</button>
        </form>
        <form method="post" action="/stop" style="display:inline">
          <button class="btn btn-stop" type="submit">🔴 STOP BOT</button>
        </form>
        <div class="ms-3 align-self-center">Worker status: <strong id="status">{{ status }}</strong></div>
      </div>

      <div class="card">
        <div class="card-body">
          <h5 class="card-title">Live Logs</h5>
          <div id="logbox" class="log-box"></div>
          <div class="mt-2">
            <a class="btn btn-sm btn-outline-light" href="/download_log">Download full log</a>
          </div>
        </div>
      </div>

    </div>

    <script>
      // SSE for logs
      const evtSource = new EventSource('/stream');
      const logbox = document.getElementById('logbox');
      evtSource.onmessage = function(e) {
        logbox.innerText = (logbox.innerText ? logbox.innerText + '
' : '') + e.data;
        logbox.scrollTop = logbox.scrollHeight;
      };

      // update status periodically
      async function updateStatus(){
        const r = await fetch('/status');
        const j = await r.json();
        document.getElementById('status').innerText = j.running ? 'running' : 'stopped';
      }
      setInterval(updateStatus, 3000);
      updateStatus();
    </script>
  </body>
</html>
"""


@app.route('/')
def index():
    username = account_credentials.get('username')
    msgs_text = '
'.join(messages)
    return render_template_string(DASHBOARD_HTML,
                                  username=username,
                                  messages_text=msgs_text,
                                  targets=','.join(config.get('targets', [])),
                                  group_ids=','.join(config.get('group_ids', [])),
                                  min_delay=config.get('min_delay'),
                                  max_delay=config.get('max_delay'),
                                  cyclone_pattern=','.join(str(x) for x in config.get('cyclone_pattern', [])),
                                  cyclone_jitter=config.get('cyclone_jitter'),
                                  status='running' if worker_running else 'stopped')


@app.route('/save_account', methods=['POST'])
def save_account():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    if not username or not password:
        append_log('Account save failed: username/password required')
        return redirect(url_for('index'))
    account_credentials['username'] = username
    account_credentials['password'] = password
    append_log('Account credentials saved in memory')
    # Try to create session immediately (non-blocking but attempt)
    try:
        if Client is not None:
            # create session file
            cl = ensure_client(username, password)
            append_log('Session created/validated on save')
    except Exception as e:
        append_log(f'Warning: session creation failed on save: {e}')
    return redirect(url_for('index'))


@app.route('/upload_messages', methods=['POST'])
def upload_messages():
    global messages
    text = request.form.get('messages_text', '').strip()
    file = request.files.get('messages_file')
    if file and file.filename.lower().endswith('.txt'):
        stream = TextIOWrapper(file.stream, encoding='utf-8', errors='ignore')
        uploaded = [ln.rstrip('
') for ln in stream if ln.strip()]
        messages = uploaded
        append_log(f'Messages uploaded ({len(messages)} lines)')
    else:
        messages = [ln for ln in text.splitlines() if ln.strip()]
        append_log(f'Messages saved from textarea ({len(messages)} lines)')
    return redirect(url_for('index'))


@app.route('/save_config', methods=['POST'])
def save_config():
    config['targets'] = [t.strip() for t in request.form.get('targets', '').split(',') if t.strip()]
    config['group_ids'] = [g.strip() for g in request.form.get('group_ids', '').split(',') if g.strip()]
    try:
        config['min_delay'] = float(request.form.get('min_delay', config.get('min_delay', 3.0)))
        config['max_delay'] = float(request.form.get('max_delay', config.get('max_delay', 6.0)))
    except Exception:
        pass
    try:
        config['cyclone_pattern'] = [float(x) for x in request.form.get('cyclone_pattern', ','.join(str(x) for x in config.get('cyclone_pattern', []))).split(',') if x.strip()]
    except Exception:
        pass
    try:
        config['cyclone_jitter'] = float(request.form.get('cyclone_jitter', config.get('cyclone_jitter', 0.25)))
    except Exception:
        pass
    append_log('Config saved')
    return redirect(url_for('index'))


@app.route('/start', methods=['POST'])
def start():
    global worker_thread, worker_stop_event, worker_running
    with worker_lock:
        if worker_running:
            append_log('Start requested but worker already running')
            return redirect(url_for('index'))
        username = account_credentials.get('username')
        password = account_credentials.get('password')
        if not username or not password:
            append_log('Start failed: account not configured')
            return redirect(url_for('index'))
        # reset stop event
        worker_stop_event.clear()
        worker_thread = threading.Thread(target=worker_loop, args=(username, password), daemon=True)
        worker_thread.start()
        worker_running = True
        append_log('Worker thread launched')
        return redirect(url_for('index'))


@app.route('/stop', methods=['POST'])
def stop():
    global worker_stop_event
    if not worker_running:
        append_log('Stop requested but worker is not running')
        return redirect(url_for('index'))
    worker_stop_event.set()
    append_log('Stop signal sent to worker')
    return redirect(url_for('index'))


@app.route('/status')
def status():
    return jsonify({'running': worker_running})


@app.route('/download_log')
def download_log():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'a').close()
    return send_from_directory(LOGS_DIR, os.path.basename(LOG_FILE), as_attachment=True)


@app.route('/stream')
def stream():
    def event_stream():
        # send last 200 lines first
        with log_condition:
            last = log_lines[-200:]
        for l in last:
            yield f'data: {l}

'
        idx = len(last)
        while True:
            with log_condition:
                log_condition.wait(timeout=10)
                new = log_lines[idx:]
            if new:
                for l in new:
                    yield f'data: {l}

'
                idx += len(new)
            # keep connection alive
            yield ': keep-alive

'
    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')


# -------------------------
# Startup
# -------------------------
if __name__ == '__main__':
    append_log('App starting up')
    if Client is None:
        append_log('WARNING: instagrapi not installed. Add it to requirements.txt')
    # ensure files exist
    open(LOG_FILE, 'a').close()
    # Run with python app.py
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port)

