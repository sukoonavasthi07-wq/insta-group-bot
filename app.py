import os
import time
import json
import random
import threading
from flask import Flask, request, render_template_string, Response, redirect
from instagrapi import Client

# ==========================================
# GLOBALS
# ==========================================

app = Flask(__name__)
LOG_BUFFER = []
STOP_EVENT = threading.Event()
WORKER_THREAD = None
CLIENT = None

SESSION_DIR = "sessions"
SESSION_FILE = f"{SESSION_DIR}/session.json"

if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

# ==========================================
# HTML TEMPLATE (Bootstrap 5)
# ==========================================

PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Group Bot</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f5f7fa; }
        .card { border-radius: 20px; }
        .log-box {
            width: 100%;
            height: 300px;
            background: #000;
            color: #0f0;
            padding: 10px;
            font-family: monospace;
            overflow-y: scroll;
            border-radius: 10px;
        }
        .header {
            padding: 20px;
            text-align: center;
        }
    </style>
</head>

<body>
<div class="container mt-4">
    <div class="header">
        <h2 class="fw-bold">Instagram Group Message Bot</h2>
        <p class="text-muted">Login → Auto Session → Start / Stop → Live Logs → Delays</p>
    </div>

    <div class="card shadow p-4">
        <form method="POST" enctype="multipart/form-data">

            <h5 class="fw-bold">Instagram Login</h5>
            <input name="username" class="form-control mt-2" placeholder="Instagram Username" required>
            <input name="password" class="form-control mt-2" placeholder="Instagram Password" type="password" required>

            <hr>

            <h5 class="fw-bold">Message</h5>
            <textarea name="message" class="form-control mt-2" placeholder="Type your message"></textarea>

            <p class="text-center mt-2">OR</p>

            <label class="form-label fw-bold">Upload .txt Message File:</label>
            <input type="file" class="form-control" name="msgfile">

            <hr>

            <h5 class="fw-bold">Group Thread IDs (one per line)</h5>
            <textarea name="threads" class="form-control mt-2" placeholder="3402823668417...."></textarea>

            <hr>

            <h5>Delay (Seconds)</h5>
            <input name="delay" class="form-control" placeholder="5">

            <h5 class="mt-3">Cyclone Delay Range</h5>
            <input name="cyclone_min" class="form-control mt-2" placeholder="Min Random Delay (e.g. 3)">
            <input name="cyclone_max" class="form-control mt-2" placeholder="Max Random Delay (e.g. 10)">

            <hr>

            <button name="action" value="start" class="btn btn-primary w-100 py-2 mt-2">Start Bot</button>
            <button name="action" value="stop" class="btn btn-danger w-100 py-2 mt-2">Stop Bot</button>
        </form>
    </div>

    <div class="card shadow p-4 mt-4">
        <h5 class="fw-bold">Live Logs</h5>
        <div id="logs" class="log-box"></div>
    </div>
</div>

<script>
    var logBox = document.getElementById("logs");
    var evtSource = new EventSource("/logs");

    evtSource.onmessage = function(event) {
        logBox.innerHTML += event.data + "<br>";
        logBox.scrollTop = logBox.scrollHeight;
    };
</script>

</body>
</html>
"""

# ==========================================
# LOGGING HELPER
# ==========================================

def log(msg):
    print(msg)
    LOG_BUFFER.append(msg)

# ==========================================
# INSTAGRAM LOGIN + SESSION HANDLING
# ==========================================

def get_client(username, password):
    global CLIENT

    cl = Client()

    # LOAD session if exists
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            log("Loaded session.json & logged in.")
        except:
            log("Session invalid. Logging in fresh.")
            cl = Client()
            cl.login(username, password)
            cl.dump_settings(SESSION_FILE)
            log("New session.json created.")
    else:
        log("No session found — logging in fresh.")
        cl.login(username, password)
        cl.dump_settings(SESSION_FILE)
        log("session.json created.")

    CLIENT = cl
    return cl

# ==========================================
# WORKER THREAD: SENDS MESSAGES
# ==========================================

def start_worker(username, password, threads, message, delay, min_cyc, max_cyc):
    STOP_EVENT.clear()
    client = get_client(username, password)

    log("Bot started.")

    while not STOP_EVENT.is_set():
        for thread_id in threads:
            if STOP_EVENT.is_set():
                break

            try:
                client.direct_send(message, [], thread_ids=[thread_id])
                log(f"Sent to {thread_id}")
            except Exception as e:
                log(f"Error sending to {thread_id}: {e}")

            # base delay
            time.sleep(delay)

            # cyclone random delay
            cyclone = random.randint(min_cyc, max_cyc)
            log(f"Cyclone delay: {cyclone}s")
            time.sleep(cyclone)

    log("Bot stopped.")

# ==========================================
# ROUTES
# ==========================================

@app.route("/", methods=["GET", "POST"])
def index():
    global WORKER_THREAD

    if request.method == "POST":

        if request.form.get("action") == "stop":
            STOP_EVENT.set()
            log("Stop requested by user.")
            return redirect("/")

        if request.form.get("action") == "start":
            username = request.form.get("username").strip()
            password = request.form.get("password").strip()

            # message from box OR file
            message = request.form.get("message").strip()
            file = request.files.get("msgfile")
            if file and file.filename:
                message = file.read().decode("utf-8")

            threads = [t.strip() for t in request.form.get("threads").split("\n") if t.strip()]

            delay = int(request.form.get("delay") or 5)
            min_c = int(request.form.get("cyclone_min") or 3)
            max_c = int(request.form.get("cyclone_max") or 10)

            # start worker
            WORKER_THREAD = threading.Thread(
                target=start_worker,
                args=(username, password, threads, message, delay, min_c, max_c),
                daemon=True
            )
            WORKER_THREAD.start()
            return redirect("/")

    return render_template_string(PAGE)

# ==========================================
# LIVE LOG STREAM
# ==========================================

@app.route("/logs")
def stream_logs():
    def event_stream():
        last_index = 0
        while True:
            if len(LOG_BUFFER) > last_index:
                msg = LOG_BUFFER[last_index]
                last_index += 1
                yield f"data: {msg}\n\n"
            time.sleep(0.5)

    return Response(event_stream(), mimetype="text/event-stream")

# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
