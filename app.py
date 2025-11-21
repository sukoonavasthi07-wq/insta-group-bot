# ============================
# app.py
# ============================

from flask import Flask, render_template, request, jsonify, session
from flask import Response
import os, threading, time, json, random
from pathlib import Path

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "super_secret_key_123"

BOT_RUNNING = False
LOG_QUEUE = []
THREAD = None

SESSIONS_DIR = "sessions"
Path(SESSIONS_DIR).mkdir(exist_ok=True)

# --------------------------------------
# Utility: Push logs
# --------------------------------------
def log(msg):
    LOG_QUEUE.append(msg)
    print(msg)

# --------------------------------------
# SSE log streaming
# --------------------------------------
@app.route('/logs')
def stream_logs():
    def event_stream():
        last_index = 0
        while True:
            if last_index < len(LOG_QUEUE):
                data = LOG_QUEUE[last_index]
                last_index += 1
                yield f"data: {data}\n\n"
            time.sleep(0.5)
    return Response(event_stream(), mimetype="text/event-stream")

# --------------------------------------
# Bot thread
# --------------------------------------
def bot_worker(username, password, message, groups, delay, cmin, cmax):
    global BOT_RUNNING

    log("Starting bot worker...")
    time.sleep(1)

    # Simulate session.json creation
    session_file = f"sessions/{username}_session.json"
    if not os.path.exists(session_file):
        with open(session_file, 'w') as f:
            json.dump({"username": username, "session": "mock_session"}, f)
        log(f"Session created for {username}")
    else:
        log("Loaded existing session.json")

    # Main loop
    while BOT_RUNNING:
        for gid in groups:
            if not BOT_RUNNING:
                break

            msg = random.choice(message) if isinstance(message, list) else message

            log(f"Sending to {gid}: {msg}")
            time.sleep(int(delay))
            extra = random.randint(cmin, cmax)
            log(f"Cyclone delay: {extra}s")
            time.sleep(extra)

        time.sleep(1)

    log("Bot stopped.")

# --------------------------------------
# Home UI
# --------------------------------------
@app.route('/')
def index():
    return render_template("index.html", session=session)

# --------------------------------------
# Start bot
# --------------------------------------
@app.route('/start', methods=['POST'])
def start():
    global BOT_RUNNING, THREAD

    session['username'] = request.form.get("username")
    session['password'] = request.form.get("password")
    session['message'] = request.form.get("message")
    session['group_ids'] = request.form.get("group_ids")
    session['delay'] = request.form.get("delay")
    session['cyclone_min'] = request.form.get("cyclone_min")
    session['cyclone_max'] = request.form.get("cyclone_max")

    username = session['username']
    password = session['password']
    message = session['message'].split("\n")
    groups = session['group_ids'].split("\n")
    delay = int(session['delay'])
    cmin = int(session['cyclone_min'])
    cmax = int(session['cyclone_max'])

    if not BOT_RUNNING:
        BOT_RUNNING = True
        THREAD = threading.Thread(target=bot_worker,
                                  args=(username, password, message, groups, delay, cmin, cmax),
                                  daemon=True)
        THREAD.start()

    return jsonify({"status": "started"})

# --------------------------------------
# Stop bot
# --------------------------------------
@app.route('/stop', methods=['POST'])
def stop():
    global BOT_RUNNING
    BOT_RUNNING = False
    return jsonify({"status": "stopped"})

# --------------------------------------
# Port binding for Render
# --------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# ============================
# templates/index.html
# ============================

"""
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Group Bot</title>
    <style>
        body {
            background: #0c0f1a;
            color: #fff;
            font-family: Arial;
            padding: 20px;
        }
        .card {
            backdrop-filter: blur(10px);
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.2);
            padding: 20px;
            border-radius: 16px;
            max-width: 700px;
            margin: auto;
        }
        input, textarea {
            width: 100%;
            padding: 10px;
            margin-top: 10px;
            border-radius: 10px;
            border: none;
            background: rgba(255,255,255,0.1);
            color: #fff;
        }
        button {
            padding: 14px;
            width: 48%;
            border: none;
            font-size: 16px;
            border-radius: 12px;
            cursor: pointer;
            margin-top: 15px;
        }
        .start { background: #0f0; color: #000; }
        .stop  { background: #f00; color: #fff; }
        #logbox {
            margin-top: 20px;
            padding: 10px;
            background: rgba(0,0,0,0.4);
            height: 250px;
            overflow-y: scroll;
            border-radius: 10px;
            font-family: monospace;
            font-size: 14px;
        }
    </style>
</head>
<body>

<div class="card">
    <h2>Instagram Group Messaging Bot</h2>

    <label>Username</label>
    <input name="username" id="username" value="{{ session.get('username','') }}">

    <label>Password</label>
    <input name="password" id="password" type="password" value="{{ session.get('password','') }}">

    <label>Message</label>
    <textarea id="message">{{ session.get('message','') }}</textarea>

    <label>Group IDs</label>
    <textarea id="group_ids">{{ session.get('group_ids','') }}</textarea>

    <label>Delay</label>
    <input id="delay" type="number" value="{{ session.get('delay','') }}">

    <label>Cyclone Min</label>
    <input id="cyclone_min" type="number" value="{{ session.get('cyclone_min','') }}">

    <label>Cyclone Max</label>
    <input id="cyclone_max" type="number" value="{{ session.get('cyclone_max','') }}">

    <br>
    <button class="start" onclick="startBot()">START</button>
    <button class="stop" onclick="stopBot()">STOP</button>

    <div id="logbox"></div>
</div>

<script>
function startBot() {
    const fd = new FormData();
    fd.append("username", document.getElementById('username').value);
    fd.append("password", document.getElementById('password').value);
    fd.append("message", document.getElementById('message').value);
    fd.append("group_ids", document.getElementById('group_ids').value);
    fd.append("delay", document.getElementById('delay').value);
    fd.append("cyclone_min", document.getElementById('cyclone_min').value);
    fd.append("cyclone_max", document.getElementById('cyclone_max').value);

    fetch('/start', { method: 'POST', body: fd });
}
function stopBot() {
    fetch('/stop', { method: 'POST' });
}

// LIVE LOG STREAM
const evtSource = new EventSource('/logs');
evtSource.onmessage = function(event) {
    const logBox = document.getElementById('logbox');
    logBox.innerHTML += event.data + "<br>";
    logBox.scrollTop = logBox.scrollHeight;
};
</script>

</body>
</html>
"""
