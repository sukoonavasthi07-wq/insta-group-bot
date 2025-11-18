# app.py
"""
Instagram DM Bot - Flask backend

Endpoints:
- POST /send    : start sending messages (accepts JSON config). If no JSON provided,
                  falls back to environment variables (single-account).
- POST /stop    : stop the running job.
- GET  /status  : return current status info.
- GET  /logs    : return recent logs (plain text).
- GET  /        : small landing page.

Behavior:
- Supports multiple accounts (accounts -> session files stored under ./sessions/)
- Auto-creates/loads session.json per account
- Cyclone delays (pattern + jitter) and simple min/max delay support
- Exponential backoff on send failures
- Live logs stored to logs/live.log and in-memory (last N lines)
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

from flask import Flask, jsonify, request, send_file, abort

# third-party
try:
    from instagrapi import Client
except Exception as e:
    raise RuntimeError("Missing dependency 'instagrapi'. Install requirements.") from e

# -----------------------
# Directories / Files
# -----------------------
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
SESSION_DIR = BASE_DIR / "sessions"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "live.log"

# -----------------------
# App & Globals
# -----------------------
app = Flask(__name__)
run_lock = Lock()
runner = None  # will hold BotRunner instance

# Keep in-memory logs for quick UI access
MAX_IN_MEMORY_LOGS = 2000
in_memory_logs = deque([], maxlen=MAX_IN_MEMORY_LOGS)


# -----------------------
# Logging helpers
# -----------------------
def append_log(line: str, to_console: bool = True):
    t = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    final = f"[{t} UTC] {line}"
    in_memory_logs.append(final)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(final + "\n")
    except Exception:
        # don't crash logging
        pass
    if to_console:
        print(final)


# -----------------------
# Bot Runner
# -----------------------
class BotRunner:
    def __init__(self):
        self._thread = None
        self._stop_event = Event()
        self._running = False
        self._status_lock = Lock()
        self._status = {
            "status": "idle",
            "time": None,
            "summary": "Not started",
            "current_account": None,
            "sent_count": 0,
            "failed_count": 0,
        }
        self._config = None

    def status(self):
        with self._status_lock:
            return dict(self._status)

    def start(self, config: Dict[str, Any], single_run: bool = False):
        with run_lock:
            if self._running:
                append_log("Start requested but runner already running.")
                return {"ok": False, "reason": "already_running"}
            self._stop_event.clear()
            self._running = True
            self._config = config
            self._status.update({
                "status": "running",
                "time": datetime.utcnow().isoformat() + "Z",
                "summary": "Started",
                "sent_count": 0,
                "failed_count": 0,
            })
            self._thread = Thread(target=self._run_main, args=(config, single_run), daemon=True)
            self._thread.start()
            append_log("BotRunner started.")
            return {"ok": True, "message": "started"}

    def stop(self):
        append_log("Stop requested.")
        self._stop_event.set()
        self._status.update({"status": "stopping"})
        # join thread with small timeout (non-blocking)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._running = False
        self._status.update({"status": "stopped", "summary": "Stopped by user"})
        append_log("BotRunner stopped.")
        return {"ok": True}

    def _set_status(self, **kwargs):
        with self._status_lock:
            self._status.update(kwargs)

    # -----------------------
    # Session helpers
    # -----------------------
    def _session_file_for(self, username: str) -> str:
        safe = username.replace("@", "").replace(" ", "_")
        return str(SESSION_DIR / f"{safe}_session.json")

    def _ensure_client_for(self, account: Dict[str, str]) -> Client:
        """
        Ensures a logged-in Client for a given account.
        account: {"username": "...", "password": "..."}
        Returns an instagrapi.Client
        """
        username = account.get("username")
        password = account.get("password", "")
        if not username:
            raise ValueError("Account missing username")

        append_log(f"Preparing client for {username}")
        client = Client()
        session_file = self._session_file_for(username)
        try:
            if os.path.exists(session_file):
                try:
                    client.load_settings(session_file)
                    # attempt to re-login / verify session — instagrapi will use stored cookies
                    client.login(username, password)
                    client.dump_settings(session_file)
                    append_log(f"Loaded existing session for {username}")
                    return client
                except Exception:
                    append_log(f"Could not reuse session for {username}. Will attempt fresh login.")
            # fresh login
            client = Client()
            append_log(f"Logging in {username} (fresh)")
            client.login(username, password)
            client.dump_settings(session_file)
            append_log(f"Logged in and saved session for {username}")
            return client
        except Exception as e:
            append_log(f"Login failed for {username}: {e}")
            raise

    # -----------------------
    # Delay / backoff helpers
    # -----------------------
    def _cyclone_delay(self, pattern: List[float], jitter: float, index: int, min_delay: float, max_delay: float) -> float:
        if pattern:
            base = float(pattern[index % len(pattern)])
        else:
            base = random.uniform(min_delay or 1.0, max_delay or 4.0)
        j = (jitter or 0.0) * base
        delay = base + random.uniform(-j, j)
        return max(0.2, float(delay))

    def _exponential_backoff(self, attempt: int, base_backoff: float = 2.0) -> float:
        backoff = base_backoff * (2 ** (attempt - 1))
        backoff += random.uniform(0, backoff * 0.25)
        return backoff

    # -----------------------
    # Core sending loop
    # -----------------------
    def _run_main(self, config: Dict[str, Any], single_run: bool):
        """
        config keys (all optional; validated/coerced before calling):
        - accounts: list of {"username":str, "password":str}
        - messages: list[str]
        - recipients: list[str]
        - custom_name: str
        - min_delay, max_delay: float
        - cyclone_pattern: list[float]
        - cyclone_jitter: float
        - max_retries: int
        - base_backoff: float
        - send_to_groups: bool (groups provided in recipients)
        """
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
                append_log("No messages to send; aborting run.")
                self._set_status(status="idle", summary="no_messages")
                self._running = False
                return

            if not recipients:
                append_log("No recipients provided; aborting run.")
                self._set_status(status="idle", summary="no_recipients")
                self._running = False
                return

            # Prepare clients for all accounts (lazy login on demand)
            clients_map = {}  # username -> Client
            account_index = 0
            msg_index = 0
            sent_count = 0
            failed_count = 0

            append_log(f"Begin sending loop. single_run={single_run}. Recipients={len(recipients)} Accounts={len(accounts)}")

            while not self._stop_event.is_set():
                # Stop after one full pass if single_run true
                if single_run and account_index >= len(recipients):
                    append_log("Single-run completed.")
                    break

                # pick next recipient
                recipient = recipients[account_index % len(recipients)]
                message = messages[msg_index % len(messages)]
                msg_index += 1

                # allow template replacement for custom_name and placeholder {name}
                if custom_name:
                    message = message.replace("{name}", custom_name)

                # choose account in round-robin
                if accounts:
                    account = accounts[account_index % len(accounts)]
                else:
                    # fallback to ENV single-account
                    env_user = os.getenv("INSTAGRAM_USERNAME")
                    env_pass = os.getenv("INSTAGRAM_PASSWORD")
                    if not (env_user and env_pass):
                        append_log("No account configured (and no INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD env). Aborting.")
                        self._set_status(status="idle", summary="no_account")
                        break
                    account = {"username": env_user, "password": env_pass}

                account_username = account.get("username")
                self._set_status(current_account=account_username)
                # prepare client if not already
                if account_username not in clients_map:
                    try:
                        clients_map[account_username] = self._ensure_client_for(account)
                    except Exception as e:
                        append_log(f"Skipping account {account_username} due to login error: {e}")
                        failed_count += 1
                        account_index += 1
                        # move to next recipient/account
                        time.sleep(1.0)
                        continue

                client = clients_map[account_username]

                # Resolve and send with retries
                success = False
                attempt = 0
                while attempt < max_retries and not success and not self._stop_event.is_set():
                    attempt += 1
                    try:
                        # Determine if recipient looks like a group id (all digits) or username
                        if recipient.isdigit():
                            # group thread id - instagrapi expects thread_id for group messages
                            thread_id = int(recipient)
                            # instagrapi direct_send can accept thread_id via client.direct_send(message, thread_ids=[thread_id])
                            # but API varies; we attempt direct_send to thread
                            client.direct_send(message, thread_ids=[thread_id])
                        else:
                            # username -> convert to user_id
                            to_user_id = client.user_id_from_username(recipient)
                            client.direct_send(message, [to_user_id])

                        append_log(f"Sent to {recipient} using {account_username} (attempt {attempt})")
                        sent_count += 1
                        success = True
                    except Exception as e:
                        append_log(f"Send attempt {attempt} to {recipient} failed: {e}")
                        # If maxed out, mark failure
                        if attempt >= max_retries:
                            append_log(f"Max retries reached for {recipient}; moving on.")
                            failed_count += 1
                            break
                        backoff = self._exponential_backoff(attempt, base_backoff)
                        append_log(f"Retrying after backoff {backoff:.1f}s")
                        time.sleep(backoff)

                # persist session for account after sending (best-effort)
                try:
                    session_file = self._session_file_for(account_username)
                    client.dump_settings(session_file)
                except Exception:
                    pass

                self._set_status(sent_count=sent_count, failed_count=failed_count)

                # Delay before next send
                delay = self._cyclone_delay(cyclone_pattern, cyclone_jitter, msg_index, min_delay, max_delay)
                append_log(f"Delay {delay:.2f}s before next send.")
                # sleep but responsive to stop
                slept = 0.0
                step = 0.5
                while slept < delay and not self._stop_event.is_set():
                    time.sleep(min(step, delay - slept))
                    slept += step

                account_index += 1

                # break condition for single_run: perform only len(recipients) sends
                if single_run and account_index >= len(recipients):
                    append_log("Single-run finished required sends.")
                    break

            # End of sending loop
            append_log(f"Sending loop finished. sent={sent_count}, failed={failed_count}")
            self._set_status(status="idle", summary=f"sent {sent_count}, failed {failed_count}", sent_count=sent_count,
                             failed_count=failed_count, time=datetime.utcnow().isoformat() + "Z")
            self._running = False
        except Exception as e:
            append_log("Unhandled error in runner: " + str(e))
            append_log(traceback.format_exc())
            self._set_status(status="failed", summary=str(e))
            self._running = False


# -----------------------
# Flask endpoints
# -----------------------
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
def send_endpoint():
    """
    Accepts JSON config or uses env vars.
    JSON keys:
      accounts: [{username, password}, ...]
      messages: [str, ...]
      recipients: [str, ...]  (usernames or numeric group ids)
      custom_name: str
      min_delay, max_delay: floats
      cyclone_pattern: [float,...]
      cyclone_jitter: float
      max_retries: int
      base_backoff: float
      singleRun: bool  (optional)
      testOnly: bool  (optional) - do login checks and return result without sending
    """
    global runner
    payload = {}
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}

    # allow form data fallback
    if not payload and request.form:
        payload = request.form.to_dict(flat=True)

    # normalize simple fields
    single_run = bool(payload.get("singleRun") or payload.get("single_run") or payload.get("singleRun") is True)
    test_only = bool(payload.get("testOnly") or payload.get("test_only"))

    # Build config with validation/coercion
    config = {}

    # Accounts
    accounts = payload.get("accounts")
    if not accounts:
        # fallback to env single-account
        env_user = os.getenv("INSTAGRAM_USERNAME")
        env_pass = os.getenv("INSTAGRAM_PASSWORD")
        if env_user and env_pass:
            accounts = [{"username": env_user, "password": env_pass}]
    if accounts:
        validated = []
        for a in accounts:
            if isinstance(a, dict):
                if a.get("username"):
                    validated.append({"username": a.get("username"), "password": a.get("password", "")})
            else:
                # try parse "user:pass" strings
                s = str(a)
                if ":" in s:
                    u, p = s.split(":", 1)
                    validated.append({"username": u.strip(), "password": p.strip()})
        config["accounts"] = validated

    # Messages
    messages = payload.get("messages")
    if isinstance(messages, str):
        # newline separated
        messages = [m.strip() for m in messages.splitlines() if m.strip()]
    if not messages:
        # maybe messages_text or messagesFile content
        if payload.get("messages_text"):
            messages = [m.strip() for m in str(payload.get("messages_text")).splitlines() if m.strip()]
    if messages:
        config["messages"] = messages

    # Recipients
    recipients = payload.get("recipients") or payload.get("to") or payload.get("targets")
    if isinstance(recipients, str):
        recipients = [r.strip() for r in recipients.split(",") if r.strip()]
    if recipients:
        config["recipients"] = recipients

    # Other params
    def _float_or_none(k):
        v = payload.get(k)
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None

    config["custom_name"] = payload.get("custom_name") or payload.get("customName") or ""
    config["min_delay"] = _float_or_none("min_delay") or _float_or_none("minDelay") or payload.get("min_delay") or payload.get("minDelay")
    config["max_delay"] = _float_or_none("max_delay") or _float_or_none("maxDelay") or payload.get("max_delay") or payload.get("maxDelay")
    # cyclone pattern may be list or comma string
    cp = payload.get("cyclone_pattern") or payload.get("cyclonePattern") or payload.get("cyclone_pattern")
    if isinstance(cp, str):
        try:
            config["cyclone_pattern"] = [float(x.strip()) for x in cp.split(",") if x.strip()]
        except Exception:
            config["cyclone_pattern"] = []
    else:
        config["cyclone_pattern"] = cp or []
    config["cyclone_jitter"] = _float_or_none("cyclone_jitter") or _float_or_none("cycloneJitter") or 0.0
    config["max_retries"] = int(payload.get("max_retries") or payload.get("maxRetries") or 3)
    config["base_backoff"] = _float_or_none("base_backoff") or 2.0

    # Basic tests
    if not config.get("messages"):
        return jsonify({"ok": False, "reason": "no_messages", "message": "Provide messages array or messages_text"}), 400
    if not config.get("recipients"):
        return jsonify({"ok": False, "reason": "no_recipients", "message": "Provide recipients list"}), 400

    # If testOnly requested, try login on each account and return result
    if test_only:
        results = []
        for a in config.get("accounts", []):
            try:
                c = Client()
                append_log(f"Test login: attempting {a.get('username')}")
                c.login(a.get("username"), a.get("password"))
                # don't save real session during test
                results.append({"username": a.get("username"), "ok": True})
            except Exception as e:
                results.append({"username": a.get("username"), "ok": False, "error": str(e)})
        return jsonify({"ok": True, "test_results": results})

    # Start runner
    global runner
    if runner is None:
        runner = BotRunner()

    res = runner.start(config=config, single_run=single_run)
    return jsonify(res)


@app.route("/stop", methods=["POST"])
def stop_endpoint():
    global runner
    if runner is None:
        return jsonify({"ok": False, "reason": "not_running"})
    return jsonify(runner.stop())


@app.route("/status", methods=["GET"])
def status_endpoint():
    global runner
    if runner is None:
        return jsonify({"status": "idle", "summary": "not_started", "time": None})
    return jsonify(runner.status())


@app.route("/logs", methods=["GET"])
def logs_endpoint():
    """
    Return logs from in-memory buffer (most recent lines) or full file when ?full=1
    """
    full = request.args.get("full", "0") in ("1", "true", "yes")
    if full:
        try:
            return send_file(str(LOG_FILE), mimetype="text/plain", as_attachment=False, download_name="live.log")
        except Exception:
            abort(404)
    # else return last N lines as plain text
    text = "\n".join(list(in_memory_logs)[-MAX_IN_MEMORY_LOGS:])
    return text, 200, {"Content-Type": "text/plain; charset=utf-8"}


# -----------------------
# Run server
# -----------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    append_log("Starting Instagram DM Bot server")
    # create empty log file if missing
    if not LOG_FILE.exists():
        LOG_FILE.write_text("")
    app.run(host="0.0.0.0", port=port, debug=False)
