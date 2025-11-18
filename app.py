import os
import threading
import time
import json
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory

app = Flask(__name__)
BOT_RUNNING = False
LOG_FILE = "logs/live.log"

# Make log folder
os.makedirs("logs", exist_ok=True)


# -----------------------------
# LOGGING FUNCTION
# -----------------------------
def log(message):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    text = f"{timestamp} {message}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text)


# -----------------------------
# FAKE INSTAGRAM SENDER (Replace with real API)
# -----------------------------
def send_instagram_message(account, target, message):
    """
    🔴 IMPORTANT:
    Here you must integrate your INSTAGRAM PRIVATE API / IG Client code.
    Currently it only prints logs so that the UI works fully.
    """
    log(f"[{account['username']}] Sending message to {target}: {message}")
    time.sleep(1)  # simulate delay


# -----------------------------
# BOT THREAD
# -----------------------------
def bot_worker(config):
    global BOT_RUNNING

    accounts = config["accounts"]
    usernames = config["usernames"]
    groups = config["groups"]
    messages = config["messages"]
    min_delay = config["min_delay"]
    max_delay = config["max_delay"]
    cyclone_pattern = config["cyclone_pattern"]
    cyclone_jitter = config["cyclone_jitter"]

    account_index = 0
    cyclone_index = 0

    log("BOT STARTED 🔵")

    while BOT_RUNNING:
        for target in usernames + groups:

            if not BOT_RUNNING:
                break

            # Rotate account
            account = accounts[account_index]
            account_index = (account_index + 1) % len(accounts)

            # Pick message
            msg = messages[int(time.time()) % len(messages)]

            # Send
            send_instagram_message(account, target, msg)

            # Delay
            # Cyclone delay
            cyclone_delay = cyclone_pattern[cyclone_index]
            cyclone_index = (cyclone_index + 1) % len(cyclone_pattern)

            # jitter
            jitter = cyclone_delay * cyclone_jitter
            final_delay = cyclone_delay + (jitter * (1 if time.time() % 2 else -1))

            log(f"Delay applied: {final_delay:.2f} seconds")
            time.sleep(final_delay)

    log("BOT STOPPED 🔴")


# -----------------------------
# START BOT
# -----------------------------
@app.route("/start", methods=["POST"])
def start_bot():
    global BOT_RUNNING

    if BOT_RUNNING:
        return redirect(url_for("index"))

    # Read form inputs
    accounts = []
    for i in range(1, 6):
        user = request.form.get(f"acc_user_{i}")
        pwd = request.form.get(f"acc_pass_{i}")
        if user and pwd:
            accounts.append({"username": user, "password": pwd})

    usernames = request.form.get("usernames").split(",")
    groups = request.form.get("groups").split(",")

    # Messages
    text_message = request.form.get("message_box").strip()
    uploaded_file = request.files.get("message_file")

    messages = []
    if uploaded_file and uploaded_file.filename.endswith(".txt"):
        messages = uploaded_file.read().decode("utf-8").splitlines()
    if text_message:
        messages.append(text_message)

    # Cyclone
    cyclone_pattern = request.form.get("cyclone_pattern", "2,5,10").split(",")
    cyclone_pattern = [float(x) for x in cyclone_pattern]
    cyclone_jitter = float(request.form.get("cyclone_jitter", "0.25"))

    config = {
        "accounts": accounts,
        "usernames": [u.strip() for u in usernames if u.strip()],
        "groups": [g.strip() for g in groups if g.strip()],
        "messages": messages,
        "min_delay": int(request.form.get("min_delay", "3")),
        "max_delay": int(request.form.get("max_delay", "6")),
        "cyclone_pattern": cyclone_pattern,
        "cyclone_jitter": cyclone_jitter
    }

    BOT_RUNNING = True
    threading.Thread(target=bot_worker, args=(config,), daemon=True).start()

    return redirect(url_for("index"))


# -----------------------------
# STOP BOT
# -----------------------------
@app.route("/stop", methods=["POST"])
def stop_bot():
    global BOT_RUNNING
    BOT_RUNNING = False
    return redirect(url_for("index"))


# -----------------------------
# LIVE LOG VIEW
# -----------------------------
@app.route("/logs")
def view_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = f.read()
    else:
        data = ""
    return f"<pre>{data}</pre>"


# -----------------------------
# MAIN UI PAGE
# -----------------------------
@app.route("/")
def index():
    return render_template_string("""

<!DOCTYPE html>
<html>
<head>
    <title>Instagram Bot Control Panel</title>
    <meta http-equiv="refresh" content="0.2">
    <style>
        body { font-family: Arial; margin: 40px; }
        h2 { color: #333; }
        input, textarea { width: 100%; padding: 10px; margin: 5px 0; }
        .start { background: blue; color: white; padding: 15px; border: none; width: 100%; }
        .stop { background: red; color: white; padding: 15px; border: none; width: 100%; }
        .logbox { background: #000; color: #0f0; padding: 15px; height: 300px; overflow-y: scroll; }
    </style>
</head>

<body>

<h2>INSTAGRAM AUTO DM BOT – CONTROL PANEL</h2>

<form action="/start" method="POST" enctype="multipart/form-data">

<h3>Instagram Accounts (Up to 5)</h3>
{% for i in range(1,6) %}
Username {{i}}: <input name="acc_user_{{i}}">
Password {{i}}: <input name="acc_pass_{{i}}">
<hr>
{% endfor %}

<h3>Message Input</h3>
<textarea name="message_box" placeholder="Write your message..."></textarea>
<br>
Upload .txt message file:
<input type="file" name="message_file">

<h3>Targets</h3>
Usernames (comma separated):
<input name="usernames">

Group Chat IDs (comma separated):
<input name="groups">

<h3>Delays</h3>
Min Delay:
<input name="min_delay" value="3">
Max Delay:
<input name="max_delay" value="6">

<h3>Cyclone Delays</h3>
Cyclone Pattern (comma separated):
<input name="cyclone_pattern" value="2,5,10">
Cyclone Jitter:
<input name="cyclone_jitter" value="0.25">

<button class="start">🔵 START BOT</button>
</form>

<form action="/stop" method="POST">
<button class="stop">🔴 STOP BOT</button>
</form>

<h3>Live Logs</h3>
<div class="logbox">
<iframe src="/logs" style="width:100%; height:100%; border:none;"></iframe>
</div>

</body>
</html>

    """)


# RUN WITH python app.py
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
