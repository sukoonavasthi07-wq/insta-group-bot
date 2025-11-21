import os
import threading
import time
import random
from flask import Flask, render_template_string, request, Response
from instagrapi import Client

# Ensure sessions folder exists
os.makedirs('sessions', exist_ok=True)
SESSION_PATH = 'sessions/session.json'

app = Flask(__name__)

# Globals
client = None
bot_running = False
stop_event = threading.Event()
log_buffer = []

# Utility: log to buffer

def add_log(msg):
    log_buffer.append(msg)
    print(msg)

# Login + session loader

def ensure_client(username, password):
    global client
    cl = Client()

    if os.path.exists(SESSION_PATH):
        try:
            cl.load_settings(SESSION_PATH)
            cl.login(username, password)
            add_log("[SESSION] Loaded existing session.json and logged in.")
            client = cl
            return cl
        except Exception as e:
            add_log(f"[SESSION ERROR] Failed to load session.json: {e}")

    # Otherwise login fresh
    try:
        cl.login(username, password)
        cl.dump_settings(SESSION_PATH)
        add_log("[SESSION] New session.json created.")
        client = cl
        return cl
    except Exception as e:
        add_log(f"[LOGIN ERROR] {e}")
        return None

# Message sender worker thread

def worker(username, password, message, group_ids, base_delay, min_cyc, max_cyc):
    global bot_running
    bot_running = True
    stop_event.clear()

    cl = ensure_client(username, password)
    if not cl:
        add_log("[FATAL] Login failed. Cannot start bot.")
        bot_running = False
        return

    add_log("[BOT] Started.")

    while not stop_event.is_set():
        for gid in group_ids:
            if stop_event.is_set():
                break

            try:
                cl.direct_send(message, thread_ids=[gid])
                add_log(f"[SENT] Message sent to group ID: {gid}")
            except Exception as e:
                add_log(f"[ERROR] Failed to send to {gid}: {e}")

            # Apply delays
            add_log(f"[DELAY] Base delay {base_delay}s")
            time.sleep(base_delay)

            cyclone = random.randint(min_cyc, max_cyc)
            add_log(f"[CYCLONE] Extra delay {cyclone}s")
            time.sleep(cyclone)

    bot_running = False
    add_log("[BOT] Stopped.")

# Live logs via SSE

def stream_logs():
    last = 0
    while True:
        while last < len(log_buffer):
            data = log_buffer[last]
            last += 1
            yield f"data: {data}\n\n"
        time.sleep(0.3)

# UI Page (Bootstrap)
html = """
<!DOCTYPE html>
<html>
<head>
<title>Instagram Group Bot</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background: #f0f2f5; }
.card { border-radius: 16px; }
.log-box {
    height: 300px;
    background: #000;
    color: #0f0;
    padding: 10px;
    overflow-y: scroll;
    border-radius: 10px;
}
</style>
</head>
<body class="p-4">
<div class="container">
    <h2 class="mb-4 text-center">Instagram Group Message Bot</h2>

    <div class="card p-4 shadow">
        <form method="POST" enctype="multipart/form-data">
            <h5>Login Details</h5>
            <input class="form-control mb-2" name="username" placeholder="Instagram Username" required>
            <input class="form-control mb-3" name="password" placeholder="Instagram Password" type="password" required>

            <h5>Message</h5>
            <textarea class="form-control mb-2" name="message" placeholder="Enter message..."></textarea>
            <label>Or upload message file (.txt)</label>
            <input type="file" class="form-control mb-3" name="msgfile">

            <h5>Group Thread IDs (one per line)</h5>
            <textarea class="form-control mb-3" name="groups" required></textarea>

            <h5>Delays</h5>
            <input class="form-control mb-2" name="base_delay" placeholder="Base Delay (seconds)" required>
            <input class="form-control mb-2" name="min_cyc" placeholder="Min Cyclone Delay" required>
            <input class="form-control mb-3" name="max_cyc" placeholder="Max Cyclone Delay" required>

            <button name="action" value="start" class="btn btn-primary w-100 mb-2">START BOT</button>
            <button name="action" value="stop" class="btn btn-danger w-100">STOP BOT</button>
        </form>
    </div>

    <h4 class="mt-4">Live Logs</h4>
    <div class="log-box" id="logs"></div>
</div>

<script>
var logBox = document.getElementById("logs");
var evt = new EventSource("/logs");

evt.onmessage = function(e) {
    logBox.innerHTML += e.data + "<br>";
    logBox.scrollTop = logBox.scrollHeight;
};
</script>

</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    global bot_running

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'start' and not bot_running:
            username = request.form['username']
            password = request.form['password']

            # Get message
            message = request.form.get('message')
            msgfile = request.files.get('msgfile')
            if msgfile and msgfile.filename:
                message = msgfile.read().decode('utf-8')

            # Group IDs
            groups = request.form['groups'].splitlines()
            groups = [g.strip() for g in groups if g.strip()]

            # Delays
            base_delay = int(request.form['base_delay'])
            min_cyc = int(request.form['min_cyc'])
            max_cyc = int(request.form['max_cyc'])

            threading.Thread(target=worker, args=(username, password, message, groups, base_delay, min_cyc, max_cyc), daemon=True).start()

        elif action == 'stop':
            stop_event.set()
            add_log("[COMMAND] Stop requested.")

    return render_template_string(html)

@app.route('/logs')
def logs():
    return Response(stream_logs(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
