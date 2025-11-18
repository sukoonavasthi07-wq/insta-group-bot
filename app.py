from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
import threading, time, random, queue, os, json

app = Flask(__name__)

# =========================
# LOGGING (LIVE LOGS)
# =========================
log_q = queue.Queue()

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    log_q.put(f"[{ts}] {msg}")

def sse_stream():
    while True:
        try:
            msg = log_q.get(timeout=0.5)
            yield f"data: {msg}\n\n"
        except Exception:
            yield ": keep-alive\n\n"  # prevents Render disconnect

# =========================
# SESSION MANAGEMENT
# =========================
SESSION_FILE = "session.json"

def save_session(client):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(client.get_settings(), f)
        log("[SESSION] session.json saved")
    except Exception as e:
        log(f"[SESSION ERROR] Failed to save: {e}")

def load_session(client):
    if os.path.exists(SESSION_FILE):
        try:
            client.set_settings(json.load(open(SESSION_FILE)))
            log("[SESSION] Loaded session.json")
            return True
        except Exception as e:
            log(f"[SESSION ERROR] Failed to load: {e}")
    return False

def safe_login(username, password):
    client = Client()

    # Try session.json first
    if load_session(client):
        try:
            client.login(username, password)
            log("[LOGIN] Auto-login success using session.json")
            return client
        except Exception as e:
            log(f"[LOGIN ERROR] Auto-login failed: {e}")

    # Fresh login
    try:
        client = Client()
        client.login(username, password)
        save_session(client)
        log("[LOGIN] Fresh login success")
        return client

    except TwoFactorRequired:
        raise Exception("2FA required — disable 2FA or extend script to support it.")

    except ChallengeRequired:
        raise Exception("Instagram challenge required. Approve login in IG app (Login Activity → Yes, it was me). Then run again to save session.json.")

    except Exception as e:
        raise Exception(f"Login failed: {e}")

# =========================
# MESSAGE SENDER
# =========================

def send_group_message(client, group_id, message):
    try:
        client.direct_send(message, [group_id])
        return True, None
    except Exception as e:
        return False, str(e)

# =========================
# BOT BACKGROUND THREAD
# =========================
bot_thread = None
stop_event = threading.Event()
bot_lock = threading.Lock()

def bot_worker(cfg):
    username = cfg["username"]
    password = cfg["password"]
    group_ids = cfg["group_ids"]
    message = cfg["message"]
    delay = float(cfg["delay"])
    cyclone_delay = float(cfg["cyclone_delay"])
    custom_name = cfg.get("custom_name", username)

    log(f"Bot starting as '{custom_name}' (login: {username})")

    try:
        client = safe_login(username, password)
    except Exception as e:
        log(f"[ERROR] {e}")
        return

    cycle = 0
    while not stop_event.is_set():
        cycle += 1
        log(f"[CYCLE] Starting cycle {cycle}")

        for gid in group_ids:
            if stop_event.is_set():
                break

            d = random.uniform(max(0, delay - 1), delay + 1)
            cd = random.uniform(max(0, cyclone_delay - 2), cyclone_delay + 2)

            log(f"Waiting delay: {d:.2f}s, cyclone: {cd:.2f}s before sending to {gid}")
            time.sleep(d)
            time.sleep(cd)

            ok, err = send_group_message(client, gid, message)
            if ok:
                log(f"[SUCCESS] Message sent to {gid}")
            else:
                log(f"[SEND ERROR] {err}")

        time.sleep(random.uniform(3, 7))
        log(f"[CYCLE] Completed cycle {cycle}")

    log("Bot stopped.")
    try:
        client.logout()
    except:
        pass

# =========================
# ROUTES
# =========================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/logs")
def logs():
    return Response(stream_with_context(sse_stream()), mimetype="text/event-stream")

@app.route("/start", methods=["POST"])
def start_bot():
    global bot_thread

    with bot_lock:
        if bot_thread and bot_thread.is_alive():
            return jsonify({"status": "error", "error": "Bot already running"})

        data = request.json
        if not data:
            return jsonify({"status": "error", "error": "Missing JSON body"})

        username = data.get("username")
        password = data.get("password")
        group_ids = data.get("group_ids", [])

        if not username or not password or not group_ids:
            return jsonify({"status": "error", "error": "username, password, and group_ids required"})

        stop_event.clear()

        bot_thread = threading.Thread(target=bot_worker, args=(data,), daemon=True)
        bot_thread.start()

        return jsonify({"status": "ok", "message": "Bot started"})

@app.route("/stop", methods=["POST"])
def stop_bot():
    stop_event.set()
    return jsonify({"status": "ok", "message": "Stop signal sent"})

@app.route("/send_once", methods=["POST"])
def send_once():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    group_id = data.get("group_id")
    message = data.get("message")

    if not username or not password or not group_id:
        return jsonify({"status": "error", "error": "Missing required fields"})

    try:
        client = safe_login(username, password)
        ok, err = send_group_message(client, group_id, message)
        try:
            client.logout()
        except:
            pass
        if ok:
            return jsonify({"status": "ok", "message": "Message sent"})
        else:
            return jsonify({"status": "error", "error": err})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)
