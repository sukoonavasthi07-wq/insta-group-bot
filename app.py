# app.py
from flask import Flask, request, jsonify, Response, stream_with_context
import threading
import time
import random
import queue
import os
from instagrapi import Client

app = Flask(__name__)

# Global state for background bot and logs
bot_thread = None
bot_lock = threading.Lock()
stop_event = threading.Event()
log_queue = queue.Queue()

def log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_queue.put(f"[{timestamp}] {message}")

def sse_stream():
    # Server-Sent Events stream generator
    while True:
        try:
            msg = log_queue.get(timeout=0.5)
            yield f"data: {msg}\n\n"
        except queue.Empty:
            # Send keep-alive comment to prevent connection timeout
            yield ": keep-alive\n\n"

def login_instagram(username, password):
    cl = Client()
    # optional: you can set cl.settings or device settings here
    cl.login(username, password)
    return cl

def send_to_group(client, group_id, message, attachment_url=None):
    """
    Send a direct message to a group (thread) by its thread ID.
    If attachment_url is provided, the function will attempt to attach it as an image.
    """
    try:
        if attachment_url:
            # Download remote file temporarily, then upload as attachment
            import requests, tempfile
            r = requests.get(attachment_url, stream=True, timeout=30)
            if r.status_code == 200:
                suffix = ""
                content_type = r.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    suffix = ".jpg"
                elif "png" in content_type:
                    suffix = ".png"
                else:
                    suffix = ".dat"
                tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in r.iter_content(chunk_size=8192):
                    tf.write(chunk)
                tf.flush()
                tf.close()
                # instagrapi supports direct_send with file paths for images
                client.direct_send(message, [group_id], file= tf.name)
                os.unlink(tf.name)
            else:
                # fallback: send text only
                client.direct_send(message, [group_id])
        else:
            client.direct_send(message, [group_id])
        return True, None
    except Exception as e:
        return False, str(e)

def bot_worker(config):
    """
    Background worker that logs into Instagram and repeatedly sends messages
    until stop_event is set. config is a dict with keys:
      username, password, group_ids (list), message, attachment_url,
      delay (float), cyclone_delay (float), custom_name (string)
    """
    username = config.get("username")
    password = config.get("password")
    group_ids = config.get("group_ids", [])
    message = config.get("message", "")
    attachment_url = config.get("attachment_url")
    delay = float(config.get("delay", 3))
    cyclone_delay = float(config.get("cyclone_delay", 8))
    custom_name = config.get("custom_name", username)

    log(f"Bot starting as '{custom_name}' (login: {username})")
    try:
        client = login_instagram(username, password)
        log("Login successful.")
    except Exception as e:
        log(f"Login failed: {e}")
        return

    cycle = 0
    while not stop_event.is_set():
        cycle += 1
        for gid in group_ids:
            if stop_event.is_set():
                break
            try:
                log(f"Cycle {cycle}: preparing to send to group {gid}")
                # normal delay randomized a bit
                d = random.uniform(max(0, delay - 1), delay + 1)
                log(f"Waiting normal delay: {d:.2f}s")
                time.sleep(d)
                # cyclone long delay sometimes
                cd = random.uniform(max(0, cyclone_delay - 2), cyclone_delay + 2)
                log(f"Waiting cyclone delay: {cd:.2f}s")
                time.sleep(cd)

                ok, err = send_to_group(client, gid, message, attachment_url)
                if ok:
                    log(f"Message sent to {gid} (cycle {cycle})")
                else:
                    log(f"Failed to send to {gid}: {err}")
            except Exception as e:
                log(f"Unexpected error sending to {gid}: {e}")

        # short pause between cycles
        inter = random.uniform(2, 6)
        log(f"Cycle {cycle} completed. Sleeping {inter:.1f}s before next cycle.")
        time.sleep(inter)

    log("Bot stopped by user.")
    try:
        client.logout()
        log("Logged out from Instagram.")
    except Exception:
        pass

@app.route("/")
def index():
    # One-file UI: dark-themed dashboard (HTML + JS inline)
    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Insta Group Bot — Dashboard (Dark)</title>
<style>
:root{
  --bg:#0f1724; --panel:#0b1220; --muted:#9aa6b2; --accent:#3b82f6; --danger:#ef4444;
  --good:#10b981; --mono:Menlo,monospace;
}
body{background:linear-gradient(180deg,#071028 0%, #0b1220 100%);color:#e6eef6;font-family:Inter,system-ui,Segoe UI,Arial; margin:0; padding:24px;}
.container{max-width:980px;margin:0 auto;}
header{display:flex;align-items:center;gap:16px;margin-bottom:18px}
.logo{width:48px;height:48px;border-radius:8px;background:linear-gradient(90deg,#1e293b,#3b82f6);display:flex;align-items:center;justify-content:center;font-weight:700}
h1{margin:0;font-size:20px}
.panel{background:var(--panel);padding:16px;border-radius:12px;box-shadow:0 6px 18px rgba(2,6,23,0.6);margin-bottom:16px}
.row{display:flex;gap:12px}
.col{flex:1;min-width:0}
.label{color:var(--muted);font-size:13px;margin-bottom:6px}
.input, textarea, select{width:100%;background:#071226;border:1px solid rgba(255,255,255,0.03);padding:10px;border-radius:8px;color:#d8e6f3;font-size:14px}
textarea{min-height:100px;resize:vertical}
.btn{padding:10px 14px;border-radius:10px;border:none;font-weight:600;cursor:pointer}
.btn-blue{background:var(--accent);color:white;box-shadow:0 6px 18px rgba(59,130,246,0.18)}
.btn-red{background:var(--danger);color:white}
.small{font-size:13px;color:var(--muted)}
.logs{height:300px;overflow:auto;background:#051226;border-radius:8px;padding:10px;font-family:var(--mono);font-size:13px;color:#bfe4ff}
footer.small{color:var(--muted);text-align:center;padding-top:8px}
.top-row{display:flex;gap:12px;align-items:center}
.controls{display:flex;gap:8px;align-items:center}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">IG</div>
    <div>
      <h1>Instagram Group Bot — Dashboard (Dark)</h1>
      <div class="small">Start/stop the bot, send messages to group IDs, view live logs.</div>
    </div>
  </header>

  <div class="panel">
    <div class="row">
      <div class="col">
        <div class="label">Instagram Username</div>
        <input id="username" class="input" placeholder="your_username" />
      </div>
      <div class="col">
        <div class="label">Instagram Password</div>
        <input id="password" type="password" class="input" placeholder="your_password" />
      </div>
    </div>

    <div style="height:12px"></div>

    <div class="label">Custom Display Name (optional)</div>
    <input id="custom_name" class="input" placeholder="BotName (for logs)" />

    <div style="height:12px"></div>

    <div class="label">Group IDs (comma-separated)</div>
    <input id="group_ids" class="input" placeholder="1234567890123456789, 9876543210987654321" />

    <div style="height:12px"></div>

    <div class="label">Message to send</div>
    <textarea id="message" placeholder="Write the message to send..."></textarea>

    <div style="height:8px"></div>

    <div class="label">Attachment (optional) — enter direct image URL</div>
    <input id="attachment" class="input" placeholder="https://example.com/image.jpg" />

    <div style="height:12px"></div>

    <div class="row">
      <div class="col">
        <div class="label">Delay between messages (seconds)</div>
        <input id="delay" class="input" type="number" min="0" step="0.1" value="3" />
      </div>
      <div class="col">
        <div class="label">Cyclone delay (seconds)</div>
        <input id="cyclone_delay" class="input" type="number" min="0" step="0.1" value="8" />
      </div>
    </div>

    <div style="height:12px"></div>

    <div class="top-row">
      <div class="controls">
        <button id="startBtn" class="btn btn-blue">Start Bot</button>
        <button id="stopBtn" class="btn btn-red">Stop Bot</button>
      </div>
      <div style="flex:1"></div>
      <div class="small">Bot status: <span id="status">stopped</span></div>
    </div>
  </div>

  <div class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div><strong>Live Logs</strong> <span class="small"> (streaming)</span></div>
      <div class="small">24×7 monitor</div>
    </div>
    <div id="logs" class="logs"></div>
  </div>

  <footer class="small">Use responsibly. Avoid spamming. This tool may trigger Instagram security checks.</footer>
</div>

<script>
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusSpan = document.getElementById('status');
const logsEl = document.getElementById('logs');

function appendLog(text){
  logsEl.textContent += text + "\\n";
  logsEl.scrollTop = logsEl.scrollHeight;
}

// SSE: connect to live logs
let evtSource = null;
function connectLogs(){
  if(evtSource) return;
  evtSource = new EventSource('/logs');
  evtSource.onmessage = function(e){
    appendLog(e.data);
  };
  evtSource.onerror = function(){
    appendLog('[Logs disconnected — attempting reconnect...]');
    evtSource.close();
    evtSource = null;
    setTimeout(connectLogs, 2000);
  };
}
connectLogs();

startBtn.addEventListener('click', async ()=>{
  const payload = {
    username: document.getElementById('username').value.trim(),
    password: document.getElementById('password').value,
    custom_name: document.getElementById('custom_name').value.trim(),
    group_ids: document.getElementById('group_ids').value.split(',').map(s=>s.trim()).filter(Boolean),
    message: document.getElementById('message').value,
    attachment_url: document.getElementById('attachment').value.trim(),
    delay: parseFloat(document.getElementById('delay').value)||3,
    cyclone_delay: parseFloat(document.getElementById('cyclone_delay').value)||8
  };

  if(!payload.username || !payload.password){
    alert('Please provide username and password.');
    return;
  }
  if(!payload.group_ids.length){
    alert('Please provide at least one group ID.');
    return;
  }

  statusSpan.textContent = 'starting...';
  const resp = await fetch('/start', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const j = await resp.json();
  if(j.status === 'ok'){
    statusSpan.textContent = 'running';
    appendLog('[UI] Bot started.');
  } else {
    statusSpan.textContent = 'error';
    appendLog('[UI] Start failed: ' + (j.error||'unknown'));
    alert('Failed to start: ' + (j.error||'unknown'));
  }
});

stopBtn.addEventListener('click', async ()=>{
  statusSpan.textContent = 'stopping...';
  const resp = await fetch('/stop', {method:'POST'});
  const j = await resp.json();
  if(j.status === 'ok'){
    statusSpan.textContent = 'stopped';
    appendLog('[UI] Bot stopped.');
  } else {
    statusSpan.textContent = 'error';
    appendLog('[UI] Stop request failed.');
  }
});
</script>

</body>
</html>
"""

@app.route("/start", methods=["POST"])
def start_bot():
    global bot_thread, stop_event
    with bot_lock:
        if bot_thread and bot_thread.is_alive():
            return jsonify({"status":"error", "error":"Bot already running"})
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")
        group_ids = data.get("group_ids") or []
        message = data.get("message", "")
        attachment_url = data.get("attachment_url") or None
        delay = float(data.get("delay", 3))
        cyclone_delay = float(data.get("cyclone_delay", 8))
        custom_name = data.get("custom_name") or username

        if not username or not password or not group_ids:
            return jsonify({"status":"error", "error":"username, password and group_ids are required"})

        stop_event.clear()
        config = {
            "username": username,
            "password": password,
            "group_ids": group_ids,
            "message": message,
            "attachment_url": attachment_url,
            "delay": delay,
            "cyclone_delay": cyclone_delay,
            "custom_name": custom_name
        }
        bot_thread = threading.Thread(target=bot_worker, args=(config,), daemon=True)
        bot_thread.start()
        return jsonify({"status":"ok", "message":"Bot started"})

@app.route("/stop", methods=["POST"])
def stop_bot():
    global bot_thread, stop_event
    with bot_lock:
        if not bot_thread or not bot_thread.is_alive():
            return jsonify({"status":"error","error":"Bot is not running"})
        stop_event.set()
        # Wait briefly for thread to notice stop event
        return jsonify({"status":"ok", "message":"Stopping bot"})

@app.route("/logs")
def logs():
    return Response(stream_with_context(sse_stream()), mimetype="text/event-stream")

# Optional endpoint to send a one-off message (not looped)
@app.route("/send_once", methods=["POST"])
def send_once():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    group_id = data.get("group_id")
    message = data.get("message", "")
    attachment_url = data.get("attachment_url")

    if not username or not password or not group_id:
        return jsonify({"status":"error","error":"username, password and group_id required"})

    try:
        client = login_instagram(username, password)
        ok, err = send_to_group(client, group_id, message, attachment_url)
        try:
            client.logout()
        except Exception:
            pass
        if ok:
            return jsonify({"status":"ok","message":"Sent"})
        else:
            return jsonify({"status":"error","error":err})
    except Exception as e:
        return jsonify({"status":"error","error":str(e)})

if __name__ == "__main__":
    # Recommended port for Render is 10000 (you can change)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)
