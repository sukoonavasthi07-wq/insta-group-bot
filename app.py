# app.py
import os
import time
import json
import random
import traceback
from threading import Thread, Event, Lock
from datetime import datetime
from io import TextIOWrapper
from typing import List

from flask import (
    Flask, render_template_string, request, redirect, url_for, send_from_directory, jsonify, flash
)

# Flask-SocketIO for live log streaming
from flask_socketio import SocketIO, emit

# Instagram client
try:
    from instagrapi import Client
except Exception:
    Client = None  # we'll raise clearer error on start if missing

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# files used for persisting (optional)
ACCOUNTS_FILE = os.path.join(APP_DIR, "accounts.json")
MESSAGES_FILE = os.path.join(APP_DIR, "messages.txt")
CONFIG_FILE = os.path.join(APP_DIR, "ui_config.json")
LOG_FILE = os.path.join(APP_DIR, "logs", "live.log")
os.makedirs(os.path.join(APP_DIR, "logs"), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-please-change")
socketio = SocketIO(app, cors_allowed_origins="*")  # works with Render

# runtime state
state_lock = Lock()
worker_thread: Thread = None
worker_stop_event: Event = Event()
worker_running = False

# In-memory configuration (loaded from disk if present)
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

accounts = load_json(ACCOUNTS_FILE, [])  # list of {"username": "...", "password": "..."}
messages: List[str] = []
if os.path.exists(MESSAGES_FILE):
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            messages = [line.rstrip("\n") for line in f if line.strip()]
    except Exception:
        messages = []

ui_config = load_json(CONFIG_FILE, {
    "custom_name": "",
    "group_chat_ids": [],
    "min_delay": 3.0,
    "max_delay": 6.0,
    "cyclone_pattern": [2.0,5.0,10.0,4.0],
    "cyclone_jitter": 0.25,
    "max_retries": 4,
    "base_backoff": 2.0
})

# helper logging (sends to both file and socket)
def log(msg: str):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    # write to file
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    # emit to clients
    try:
        socketio.emit("log_line", {"line": line})
    except Exception:
        pass
    print(line)


# Utility: save accounts/messages/config optionally
def save_accounts():
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2)
    except Exception as e:
        log(f"Failed to save accounts.json: {e}")

def save_messages_file():
    try:
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            for m in messages:
                f.write(m + "\n")
    except Exception as e:
        log(f"Failed to save messages.txt: {e}")

def save_ui_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(ui_config, f, indent=2)
    except Exception as e:
        log(f"Failed to save ui_config.json: {e}")


# Cyclone delay generator
def cyclone_delay_pattern(idx: int):
    pattern = ui_config.get("cyclone_pattern") or []
    jitter_frac = float(ui_config.get("cyclone_jitter", 0.25) or 0.25)
    if not pattern:
        base = random.uniform(float(ui_config.get("min_delay", 3.0)), float(ui_config.get("max_delay", 6.0)))
    else:
        base = float(pattern[idx % len(pattern)])
    jitter = jitter_frac * base
    delay = base + random.uniform(-jitter, jitter)
    return max(0.2, delay)


def exponential_backoff(attempt: int):
    base = float(ui_config.get("base_backoff", 2.0))
    backoff = base * (2 ** (attempt - 1))
    backoff += random.uniform(0, backoff * 0.25)
    return backoff


# Per-account client creation / session management
def ensure_client_for_account(account):
    """
    Loads or creates an instagrapi.Client for the given account dict.
    Session file stored as session_{username}.json in the app dir.
    Returns a logged-in Client instance.
    """
    if Client is None:
        raise RuntimeError("instagrapi is not installed. Add it to requirements.txt and deploy.")

    username = account["username"]
    password = account.get("password", "")
    session_file = os.path.join(APP_DIR, f"session_{username}.json")
    cl = Client()
    # try load settings
    try:
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            # try a quick operation; instagrapi's login() will reuse session if valid
            cl.login(username, password)
            cl.dump_settings(session_file)
            log(f"Reused session for {username}")
            return cl
    except Exception as e:
        log(f"Could not reuse session for {username}: {e}. Will attempt fresh login.")

    # fresh login
    log(f"Logging in as {username} ...")
    cl = Client()
    cl.login(username, password)
    try:
        cl.dump_settings(session_file)
    except Exception:
        log(f"Warning: could not save session file for {username}")
    log(f"Logged in: {username}")
    return cl


# Core sending loop (runs in background thread)
def sending_worker(stop_event: Event):
    global worker_running
    log("Worker started.")
    with state_lock:
        worker_running = True

    # prepare cycle indices
    account_idx = 0
    msg_idx = 0
    send_count = 0

    # Pre-create clients list to reuse logins
    clients = []
    for acc in accounts:
        try:
            clients.append({"account": acc, "client": ensure_client_for_account(acc)})
        except Exception as e:
            log(f"Failed to init client for {acc.get('username')}: {e}")
            clients.append({"account": acc, "client": None})

    if not clients or not any(c["client"] for c in clients):
        log("No usable accounts available. Worker exiting.")
        with state_lock:
            worker_running = False
        return

    if not messages:
        log("No messages loaded. Worker exiting.")
        with state_lock:
            worker_running = False
        return

    try:
        while not stop_event.is_set():
            # choose account round-robin
            client_entry = clients[account_idx % len(clients)]
            account_idx += 1
            acc = client_entry["account"]
            cl = client_entry["client"]
            if cl is None:
                log(f"Skipping account {acc.get('username')} (no client).")
                time.sleep(1.0)
                continue

            # choose message round-robin and substitute custom name if present
            raw_msg = messages[msg_idx % len(messages)]
            msg_idx += 1
            custom_name = ui_config.get("custom_name") or ""
            if "{name}" in raw_msg and custom_name:
                message_to_send = raw_msg.replace("{name}", custom_name)
            else:
                # try placeholder @custom_name too
                if "{custom_name}" in raw_msg and custom_name:
                    message_to_send = raw_msg.replace("{custom_name}", custom_name)
                else:
                    message_to_send = raw_msg

            # send to single recipient or groups. UI will pass either recipients (usernames) in messages or group ids.
            # For this simplified worker we assume messages target a "recipient list" included in accounts config or provided via group_chat_ids in ui_config.
            # Here we support sending to "targets" loaded into ui_config["targets"] if present, else we iterate group_chat_ids.
            targets = ui_config.get("targets") or []
            group_ids = ui_config.get("group_chat_ids") or []

            # If no targets explicit, attempt sending to groups only (group ids as strings)
            if targets:
                # targets are Instagram usernames
                for t in targets:
                    if stop_event.is_set(): break
                    send_result = send_text_with_retries(cl, t, message_to_send)
                    if send_result:
                        send_count += 1
                # delay after finishing targets
            elif group_ids:
                for gid in group_ids:
                    if stop_event.is_set(): break
                    send_result = send_text_to_thread_with_retries(cl, gid, message_to_send)
                    if send_result:
                        send_count += 1
            else:
                # fallback: send to the account's own "default target" if present
                fallback_recipient = acc.get("default_target")
                if fallback_recipient:
                    send_result = send_text_with_retries(cl, fallback_recipient, message_to_send)
                    if send_result:
                        send_count += 1
                else:
                    log("No targets configured (targets or group_chat_ids). Worker sleeping.")
                    time.sleep(5.0)

            # save sessions
            try:
                session_file = os.path.join(APP_DIR, f"session_{acc.get('username')}.json")
                cl.dump_settings(session_file)
            except Exception:
                pass

            # apply cyclone delay
            d = cyclone_delay_pattern(send_count)
            log(f"Delay applied: {d:.2f}s (cyclone)")
            # sleep with stop_event responsiveness
            slept = 0.0
            while slept < d and not stop_event.is_set():
                to_sleep = min(0.5, d - slept)
                time.sleep(to_sleep)
                slept += to_sleep

    except Exception as e:
        log(f"Worker error: {e}\n{traceback.format_exc()}")
    finally:
        log("Worker stopped.")
        with state_lock:
            worker_running = False


# send functions with retries
def send_text_with_retries(client: Client, username: str, message: str):
    try:
        user_id = client.user_id_from_username(username)
    except Exception as e:
        log(f"Could not resolve user id for {username}: {e}")
        return False

    attempt = 0
    max_retries = int(ui_config.get("max_retries", 4))
    while attempt < max_retries:
        attempt += 1
        try:
            client.direct_send(message, [user_id])
            log(f"Message sent to @{username}")
            return True
        except Exception as e:
            log(f"Send attempt {attempt} to @{username} failed: {e}")
            if attempt >= max_retries:
                log(f"Giving up on @{username}")
                return False
            b = exponential_backoff(attempt)
            log(f"Retrying after backoff {b:.1f}s")
            time.sleep(b)
    return False


def send_text_to_thread_with_retries(client: Client, thread_id: str, message: str):
    attempt = 0
    max_retries = int(ui_config.get("max_retries", 4))
    while attempt < max_retries:
        attempt += 1
        try:
            client.direct_send(message, thread_ids=[thread_id])
            log(f"Message sent to thread {thread_id}")
            return True
        except Exception as e:
            log(f"Thread send attempt {attempt} to {thread_id} failed: {e}")
            if attempt >= max_retries:
                log(f"Giving up on thread {thread_id}")
                return False
            b = exponential_backoff(attempt)
            log(f"Retrying after backoff {b:.1f}s")
            time.sleep(b)
    return False


# --- Flask routes & UI ---
DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
  <title>Instagram DM Bot — Dashboard</title>
  <meta charset="utf-8" />
  <style>
    body { font-family: Arial, sans-serif; margin: 16px; background:#f7f9fc; color:#111; }
    .container { max-width:1100px; margin: 0 auto; }
    h1 { margin-bottom: 8px; }
    .card { background:white; border-radius:8px; padding:12px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); margin-bottom:12px; }
    label { display:block; margin-top:8px; font-weight:600; }
    input[type=text], input[type=password], textarea { width: 100%; padding:8px; border-radius:6px; border:1px solid #ddd; }
    .two { display:flex; gap:8px; }
    .two > div { flex:1; }
    .btn { padding:10px 14px; border-radius:8px; font-weight:700; cursor:pointer; border:none; }
    .btn.blue { background:#0b79f7; color:white; }
    .btn.red { background:#e53e3e; color:white; }
    .btn.gray { background:#e6eefb; color:#123; }
    #logs { height: 340px; overflow:auto; background:#0b1220; color:#d6f3ff; padding:8px; border-radius:6px; font-family:monospace; font-size:13px; }
    .accounts-list { font-size:14px; margin-top:6px; }
    .small { font-size:13px; color:#555; }
  </style>
  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"
    integrity="sha384-/+M7f4pJQ1sXh/J5gq4D1I1Hn6q5qX7w+fZ1K4dZ7LZp6x3Q3j0H6J6zXbqWq9aJ"
    crossorigin="anonymous"></script>
</head>
<body>
<div class="container">
  <h1>Instagram DM Bot — Dashboard</h1>

  <div class="card">
    <h3>Accounts (multiple)</h3>
    <form id="addAccountForm" method="post" action="/add_account">
      <div class="two">
        <div>
          <label>Username</label>
          <input name="username" type="text" placeholder="account_username" required/>
        </div>
        <div>
          <label>Password</label>
          <input name="password" type="password" placeholder="password" required/>
        </div>
      </div>
      <div style="margin-top:8px;">
        <button class="btn gray" type="submit">Add account</button>
        <button class="btn gray" type="button" onclick="location.href='/clear_accounts'">Clear accounts</button>
      </div>
    </form>

    <div class="accounts-list small">
      <strong>Saved accounts:</strong>
      <ul>
        {% for a in accounts %}
          <li>{{ a.username }} {% if a.default_target %} — default target: {{ a.default_target }}{% endif %}</li>
        {% else %}
          <li><em>No accounts saved</em></li>
        {% endfor %}
      </ul>
    </div>
  </div>

  <div class="card">
    <h3>Messages</h3>
    <form id="messagesForm" method="post" action="/upload_messages" enctype="multipart/form-data">
      <label>Type messages (one per line)</label>
      <textarea name="messages_text" rows="6" placeholder="Hello {name}&#10;Your update is ready...">{{ messages_text }}</textarea>
      <div style="margin-top:8px;">
        <label>or upload a <strong>messages.txt</strong> file (one message per line)</label>
        <input type="file" name="messages_file" accept=".txt" />
      </div>
      <div style="margin-top:8px;">
        <button class="btn gray" type="submit">Save messages</button>
        <button class="btn gray" type="button" onclick="location.href='/download_messages'">Download messages.txt</button>
      </div>
    </form>
    <div class="small" style="margin-top:8px;">Use <code>{name}</code> placeholder to insert custom name from config.</div>
  </div>

  <div class="card">
    <h3>Targets / Groups / Config</h3>
    <form id="configForm" method="post" action="/save_config">
      <label>Custom name (for {name} placeholder)</label>
      <input name="custom_name" type="text" value="{{ ui_config.custom_name or '' }}" />

      <label>Targets (comma-separated Instagram usernames)</label>
      <input name="targets" type="text" value="{{ targets }}" placeholder="user1,user2,user3" />

      <label>Group chat IDs (comma-separated)</label>
      <input name="group_chat_ids" type="text" value="{{ group_chat_ids }}" placeholder="1234567890,1122334455" />

      <div class="two">
        <div>
          <label>Min delay (seconds)</label>
          <input name="min_delay" type="text" value="{{ ui_config.min_delay }}" />
        </div>
        <div>
          <label>Max delay (seconds)</label>
          <input name="max_delay" type="text" value="{{ ui_config.max_delay }}" />
        </div>
      </div>

      <label>Cyclone pattern (comma-separated seconds)</label>
      <input name="cyclone_pattern" type="text" value="{{ cyclone_pattern }}" placeholder="2,5,10,4" />

      <label>Cyclone jitter (fraction, e.g. 0.25)</label>
      <input name="cyclone_jitter" type="text" value="{{ ui_config.cyclone_jitter }}" />

      <div style="margin-top:8px;">
        <button class="btn gray" type="submit">Save config</button>
      </div>
    </form>
  </div>

  <div class="card">
    <h3>Controls</h3>
    <div style="display:flex; gap:8px; align-items:center;">
      <button id="startBtn" class="btn blue" onclick="startBot()">Start Bot</button>
      <button id="stopBtn" class="btn red" onclick="stopBot()">Stop Bot</button>
      <div style="margin-left:12px;" class="small">Worker status: <span id="workerStatus">unknown</span></div>
    </div>
  </div>

  <div class="card">
    <h3>Live logs</h3>
    <div id="logs"></div>
    <div style="margin-top:8px;">
      <button class="btn gray" onclick="clearLogs()">Clear logs (client view)</button>
      <a class="btn gray" href="/download_log" style="text-decoration:none; margin-left:8px;">Download full log</a>
    </div>
  </div>

</div>

<script>
  var socket = io();

  socket.on('connect', function(){
    console.log('socket connected');
    fetch('/status').then(r => r.json()).then(j => {
      document.getElementById('workerStatus').innerText = j.running ? 'running' : 'stopped';
    });
  });

  socket.on('log_line', function(data){
    var logs = document.getElementById('logs');
    logs.innerText = (logs.innerText ? logs.innerText + "\\n" : "") + data.line;
    logs.scrollTop = logs.scrollHeight;
  });

  function startBot(){
    fetch('/start', {method:'POST'}).then(r=>r.json()).then(j=> {
      document.getElementById('workerStatus').innerText = j.ok ? 'running' : 'error';
      alert(j.message || JSON.stringify(j));
    });
  }
  function stopBot(){
    fetch('/stop', {method:'POST'}).then(r=>r.json()).then(j=> {
      document.getElementById('workerStatus').innerText = j.ok ? 'stopped' : 'error';
      alert(j.message || JSON.stringify(j));
    });
  }
  function clearLogs(){
    document.getElementById('logs').innerText = '';
  }
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    # prepare template variables
    msgs_text = "\n".join(messages)
    return render_template_string(
        DASHBOARD_HTML,
        accounts=accounts,
        messages_text=msgs_text,
        ui_config=ui_config,
        targets=",".join(ui_config.get("targets") or []),
        group_chat_ids=",".join(ui_config.get("group_chat_ids") or []),
        cyclone_pattern=",".join(str(x) for x in ui_config.get("cyclone_pattern") or [])
    )


@app.route("/add_account", methods=["POST"])
def add_account():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    if not username or not password:
        flash("username and password required")
        return redirect(url_for("dashboard"))
    accounts.append({"username": username, "password": password})
    save_accounts()
    log(f"Account added: {username}")
    return redirect(url_for("dashboard"))


@app.route("/clear_accounts")
def clear_accounts():
    global accounts
    accounts = []
    save_accounts()
    log("Cleared accounts list")
    return redirect(url_for("dashboard"))


@app.route("/upload_messages", methods=["POST"])
def upload_messages():
    # either text area or file
    text = request.form.get("messages_text", "").strip()
    file = request.files.get("messages_file")
    global messages
    if file and file.filename:
        # read file as text
        stream: TextIOWrapper = TextIOWrapper(file.stream, encoding="utf-8", errors="ignore")
        uploaded = [ln.rstrip("\n") for ln in stream if ln.strip()]
        messages = uploaded
        save_messages_file()
        log(f"Uploaded messages.txt ({len(messages)} lines)")
    else:
        # parse textarea
        messages = [ln for ln in (text.splitlines()) if ln.strip()]
        save_messages_file()
        log(f"Saved messages from textarea ({len(messages)} lines)")
    return redirect(url_for("dashboard"))


@app.route("/download_messages")
def download_messages():
    if not os.path.exists(MESSAGES_FILE):
        # create a temporary file from messages list
        save_messages_file()
    return send_from_directory(APP_DIR, "messages.txt", as_attachment=True)


@app.route("/save_config", methods=["POST"])
def save_config():
    ui_config["custom_name"] = request.form.get("custom_name", "").strip()
    targets = [t.strip() for t in request.form.get("targets", "").split(",") if t.strip()]
    ui_config["targets"] = targets
    group_ids = [g.strip() for g in request.form.get("group_chat_ids", "").split(",") if g.strip()]
    ui_config["group_chat_ids"] = group_ids
    try:
        ui_config["min_delay"] = float(request.form.get("min_delay", ui_config.get("min_delay", 3.0)))
        ui_config["max_delay"] = float(request.form.get("max_delay", ui_config.get("max_delay", 6.0)))
    except Exception:
        pass
    pat = [float(x) for x in request.form.get("cyclone_pattern", ",".join(str(x) for x in ui_config.get("cyclone_pattern", []))).split(",") if x.strip()]
    ui_config["cyclone_pattern"] = pat
    try:
        ui_config["cyclone_jitter"] = float(request.form.get("cyclone_jitter", ui_config.get("cyclone_jitter", 0.25)))
    except Exception:
        pass
    save_ui_config()
    log("Saved UI config")
    return redirect(url_for("dashboard"))


@app.route("/download_log")
def download_log():
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, "a").close()
    return send_from_directory(os.path.join(APP_DIR, "logs"), "live.log", as_attachment=True)


@app.route("/status")
def status():
    return jsonify({"running": worker_running})


@app.route("/start", methods=["POST"])
def start():
    global worker_thread, worker_stop_event, worker_running
    with state_lock:
        if worker_running:
            return jsonify({"ok": False, "message": "Worker already running."})
        # reset stop event and start thread
        worker_stop_event = Event()
        worker_thread = Thread(target=sending_worker, args=(worker_stop_event,), daemon=True)
        worker_thread.start()
        # small delay until thread sets worker_running
        return jsonify({"ok": True, "message": "Worker started."})


@app.route("/stop", methods=["POST"])
def stop():
    global worker_stop_event
    with state_lock:
        if not worker_running:
            return jsonify({"ok": True, "message": "Worker already stopped."})
        # signal stop
        worker_stop_event.set()
        return jsonify({"ok": True, "message": "Stop signal sent."})


# SocketIO route to stream last lines on connect
@socketio.on("connect")
def on_connect():
    # send last 200 lines from log file for context
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()[-200:]
            for l in lines:
                emit("log_line", {"line": l})
    except Exception:
        pass


if __name__ == "__main__":
    # ensure environment has instagrapi
    if Client is None:
        print("ERROR: instagrapi not installed. Add 'instagrapi' to requirements.txt")
    # create files if missing
    save_accounts()
    save_messages_file()
    save_ui_config()
    # run with socketio (eventlet works on Render)
    port = int(os.getenv("PORT", "5000"))
    log("Starting Flask app (development).")
    socketio.run(app, host="0.0.0.0", port=port)
