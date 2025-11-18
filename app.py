# app.py
"""
Instagram DM Sender - Flask backend using instagrapi
Implements:
  POST /send   -> start job (JSON config)
  POST /stop   -> stop job
  GET  /status -> status json
  GET  /logs   -> logs (plain text)

Session files: stored under ./sessions/<username>_session.json (auto-created)
Logs: ./logs/live.log (appends). Recent logs also kept in-memory for quick UI reads.
"""
import os
import time
import json
import random
import traceback
from threading import Thread, Lock, Event
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_file, abort, Response

try:
    from instagrapi import Client
except Exception as e:
    raise RuntimeError("Please install 'instagrapi' (see requirements.txt).") from e

# -------------------------
# Paths & globals
# -------------------------
BASE = Path(__file__).resolve().parent
LOG_DIR = BASE / "logs"
SESSION_DIR = BASE / "sessions"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "live.log"

app = Flask(__name__)
THREAD_LOCK = Lock()

# in-memory logs
MAX_IN_MEMORY = 2000
INMEM = deque(maxlen=MAX_IN_MEMORY)

def append_log(line: str):
    t = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    full = f"[{t} UTC] {line}"
    INMEM.append(full)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full + "\n")
    except Exception:
        pass
    print(full)

# -------------------------
# BotRunner
# -------------------------
class BotRunner:
    def __init__(self):
        self._thread = None
        self._stop = Event()
        self._running = False
        self._status_lock = Lock()
        self._status = {
            "status": "idle",
            "time": None,
            "summary": "not started",
            "current_account": None,
            "sent_count": 0,
            "failed_count": 0,
        }
        self._config = None

    def status(self):
        with self._status_lock:
            return dict(self._status)

    def _set_status(self, **kwargs):
        with self._status_lock:
            self._status.update(kwargs)

    def start(self, config: Dict[str, Any], single_run: bool = False):
        with THREAD_LOCK:
            if self._running:
                append_log("Start requested but already running.")
                return {"ok": False, "reason": "already_running"}
            self._stop.clear()
            self._running = True
            self._config = config
            self._set_status(status="running", time=datetime.utcnow().isoformat() + "Z",
                             summary="started", sent_count=0, failed_count=0)
            self._thread = Thread(target=self._run, args=(config, single_run), daemon=True)
            self._thread.start()
            append_log("Runner started.")
            return {"ok": True, "message": "started"}

    def stop(self):
        append_log("Stop requested.")
        self._stop.set()
        self._set_status(status="stopping")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._running = False
        self._set_status(status="stopped", summary="stopped by user")
        append_log("Runner stopped.")
        return {"ok": True}

    def _session_file(self, username: str) -> str:
        safe = username.replace("@", "").replace(" ", "_")
        return str(SESSION_DIR / f"{safe}_session.json")

    def _ensure_client(self, username: str, password: str) -> Client:
        append_log(f"Preparing client for {username}")
        client = Client()
        sess = self._session_file(username)
        try:
            if os.path.exists(sess):
                try:
                    client.load_settings(sess)
                    client.login(username, password)  # instagrapi will use settings and cookies if valid
                    client.dump_settings(sess)
                    append_log(f"Reused session for {username}")
                    return client
                except Exception:
                    append_log(f"Could not reuse session for {username}; will attempt fresh login.")
            # fresh login
            client = Client()
            client.login(username, password)
            client.dump_settings(sess)
            append_log(f"Logged in and saved session for {username}")
            return client
        except Exception as e:
            append_log(f"Login failed for {username}: {e}")
            raise

    def _cyclone(self, pattern: List[float], jitter: float, index: int, min_d: float, max_d: float) -> float:
        if pattern:
            base = float(pattern[index % len(pattern)])
        else:
            base = random.uniform(min_d or 1.0, max_d or 4.0)
        j = (jitter or 0.0) * base
        return max(0.2, base + random.uniform(-j, j))

    def _backoff(self, attempt: int, base_backoff: float = 2.0) -> float:
        b = base_backoff * (2 ** (attempt - 1))
        b += random.uniform(0, b * 0.25)
        return b

    def _run(self, config: Dict[str, Any], single_run: bool):
        try:
            accounts: List[Dict[str, str]] = config.get("accounts") or []
            messages: List[str] = config.get("messages") or []
            recipients: List[str] = config.get("recipients") or []
            custom_name: str = config.get("custom_name") or ""
            min_delay = float(config.get("min_delay") or 1.5)
            max_delay = float(config.get("max_delay") or 4.0)
            cyclone_pattern = config.get("cyclone_pattern") or []
            cyclone_jitter = float(config.get("cyclone_jitter") or 0.0)
            max_retries = int(config.get("max_retries") or 3)
            base_backoff = float(config.get("base_backoff") or 2.0)

            if not messages:
                append_log("No messages provided; aborting.")
                self._set_status(status="idle", summary="no_messages")
                self._running = False
                return
            if not recipients:
                append_log("No recipients provided; aborting.")
                self._set_status(status="idle", summary="no_recipients")
                self._running = False
                return

            clients = {}
            r_index = 0
            m_index = 0
            sent = 0
            failed = 0

            append_log(f"Starting sending loop. recipients={len(recipients)} accounts={len(accounts)} single_run={single_run}")

            # If no accounts provided, fallback to env vars if present
            if not accounts:
                env_user = os.getenv("INSTAGRAM_USERNAME")
                env_pass = os.getenv("INSTAGRAM_PASSWORD")
                if env_user and env_pass:
                    accounts = [{"username": env_user, "password": env_pass}]
                else:
                    append_log("No accounts configured and no ENV fallback. Aborting.")
                    self._set_status(status="idle", summary="no_account")
                    self._running = False
                    return

            total_to_send = len(recipients) if single_run else None

            while not self._stop.is_set():
                if single_run and r_index >= len(recipients):
                    append_log("Single-run completed.")
                    break

                recipient = recipients[r_index % len(recipients)]
                message = messages[m_index % len(messages)]
                m_index += 1

                if custom_name:
                    message = message.replace("{name}", custom_name)

                # pick account round-robin
                account = accounts[r_index % len(accounts)]
                uname = account.get("username")
                upass = account.get("password", "")
                self._set_status(current_account=uname)

                if uname not in clients:
                    try:
                        clients[uname] = self._ensure_client(uname, upass)
                    except Exception as e:
                        append_log(f"Skipping account {uname} due to login error: {e}")
                        failed += 1
                        r_index += 1
                        time.sleep(1.0)
                        continue

                client = clients[uname]

                success = False
                attempt = 0
                while attempt < max_retries and not success and not self._stop.is_set():
                    attempt += 1
                    try:
                        if recipient.isdigit():
                            # treat as group thread id
                            client.direct_send(message, thread_ids=[int(recipient)])
                        else:
                            uid = client.user_id_from_username(recipient)
                            client.direct_send(message, [uid])
                        append_log(f"Sent to {recipient} via {uname} (attempt {attempt})")
                        sent += 1
                        success = True
                    except Exception as e:
                        append_log(f"Send attempt {attempt} to {recipient} failed: {e}")
                        if attempt >= max_retries:
                            append_log(f"Failed to send to {recipient} after {attempt} attempts.")
                            failed += 1
                            break
                        back = self._backoff(attempt, base_backoff)
                        append_log(f"Retrying after backoff {back:.1f}s")
                        time.sleep(back)

                # save session best-effort
                try:
                    session_file = self._session_file(uname)
                    client.dump_settings(session_file)
                except Exception:
                    pass

                self._set_status(sent_count=sent, failed_count=failed)

                # delay
                delay = self._cyclone(cyclone_pattern, cyclone_jitter, m_index, min_delay, max_delay)
                append_log(f"Sleeping {delay:.2f}s")
                slept = 0.0
                step = 0.5
                while slept < delay and not self._stop.is_set():
                    time.sleep(min(step, delay - slept))
                    slept += step

                r_index += 1
                if single_run and total_to_send and r_index >= total_to_send:
                    append_log("Single-run finished required sends.")
                    break

            append_log(f"Run finished: sent={sent} failed={failed}")
            self._set_status(status="idle", summary=f"sent {sent}, failed {failed}", time=datetime.utcnow().isoformat() + "Z",
                             sent_count=sent, failed_count=failed)
            self._running = False
        except Exception as e:
            append_log("Runner error: " + str(e))
            append_log(traceback.format_exc())
            self._set_status(status="failed", summary=str(e))
            self._running = False

# global runner
RUNNER = BotRunner()

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET"])
def index():
    return (
        "<pre>Instagram DM Sender API\n\n"
        "POST /send   -> start job (JSON config)\n"
        "POST /stop   -> stop job\n"
        "GET  /status -> status json\n"
        "GET  /logs   -> logs (plain text)\n</pre>"
    )

@app.route("/send", methods=["POST"])
def send_route():
    """
    JSON payload expected (example):
    {
      "accounts": [{"username":"u","password":"p"}, ...],
      "messages": ["Hi {name}", "Another message"],
      "recipients": ["target1","123456789012345"],
      "custom_name": "Alex",
      "min_delay": 3,
      "max_delay": 6,
      "cyclone_pattern": [2,5,10],
      "cyclone_jitter": 0.25,
      "max_retries": 4,
      "base_backoff": 2.0,
      "singleRun": true
    }
    """
    payload = {}
    try:
        payload = request.get_json(force=True)
    except Exception:
        payload = {}

    # basic validation & normalization
    def as_list(v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return list(v)

    cfg = {}
    cfg["accounts"] = payload.get("accounts") or []
    # also support "accounts" as ["user:pass", ...]
    parsed_accounts = []
    for a in cfg["accounts"]:
        if isinstance(a, dict) and a.get("username"):
            parsed_accounts.append({"username": a.get("username"), "password": a.get("password", "")})
        elif isinstance(a, str) and ":" in a:
            u, p = a.split(":", 1)
            parsed_accounts.append({"username": u.strip(), "password": p.strip()})
    cfg["accounts"] = parsed_accounts

    messages = payload.get("messages") or payload.get("messages_text")
    if isinstance(messages, str):
        cfg["messages"] = [m.strip() for m in messages.splitlines() if m.strip()]
    else:
        cfg["messages"] = as_list(messages)

    recipients = payload.get("recipients") or payload.get("to")
    if isinstance(recipients, str):
        cfg["recipients"] = [r.strip() for r in recipients.split(",") if r.strip()]
    else:
        cfg["recipients"] = as_list(recipients)

    cfg["custom_name"] = payload.get("custom_name") or payload.get("customName") or ""
    cfg["min_delay"] = payload.get("min_delay") or payload.get("minDelay") or 1.5
    cfg["max_delay"] = payload.get("max_delay") or payload.get("maxDelay") or 4.0
    # cyclone pattern may be array or comma string
    cp = payload.get("cyclone_pattern") or payload.get("cyclonePattern") or payload.get("cyclone_pattern")
    if isinstance(cp, str):
        try:
            cfg["cyclone_pattern"] = [float(x.strip()) for x in cp.split(",") if x.strip()]
        except Exception:
            cfg["cyclone_pattern"] = []
    else:
        cfg["cyclone_pattern"] = cp or []
    cfg["cyclone_jitter"] = payload.get("cyclone_jitter") or payload.get("cycloneJitter") or 0.0
    cfg["max_retries"] = int(payload.get("max_retries") or payload.get("maxRetries") or 3)
    cfg["base_backoff"] = float(payload.get("base_backoff") or payload.get("baseBackoff") or 2.0)
    single_run = bool(payload.get("singleRun") or payload.get("single_run"))

    # if missing messages/recipients return error
    if not cfg.get("messages"):
        return jsonify({"ok": False, "reason": "no_messages"}), 400
    if not cfg.get("recipients"):
        return jsonify({"ok": False, "reason": "no_recipients"}), 400

    # if no accounts provided, runner will attempt env fallback (INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD)
    res = RUNNER.start(cfg, single_run=single_run)
    return jsonify(res)

@app.route("/stop", methods=["POST"])
def stop_route():
    return jsonify(RUNNER.stop())

@app.route("/status", methods=["GET"])
def status_route():
    return jsonify(RUNNER.status())

@app.route("/logs", methods=["GET"])
def logs_route():
    full = request.args.get("full", "0") in ("1", "true", "yes")
    if full:
        try:
            return send_file(str(LOG_FILE), mimetype="text/plain", as_attachment=False, download_name="live.log")
        except Exception:
            abort(404)
    text = "\n".join(list(INMEM)[-MAX_IN_MEMORY:])
    return Response(text, mimetype="text/plain; charset=utf-8")

# -------------------------
# Run app
# -------------------------
if __name__ == "__main__":
    if not LOG_FILE.exists():
        LOG_FILE.write_text("")
    append_log("Starting Instagram DM Sender API (instagrapi)")
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
