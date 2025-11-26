import os
import time
import json
import random
import threading
from instagrapi import Client
from fastapi import FastAPI
import uvicorn

# -------------------------
# CONFIG
# -------------------------
IG_USERNAME = os.getenv("IG_USERNAME", "dracuhikehde")
IG_PASSWORD = os.getenv("IG_PASSWORD", "Dracu420")
INSTAGRAM_THREAD_ID = os.getenv("INSTAGRAM_THREAD_ID", "788851167511644")

MESSAGES_FILE = "messages.txt"
DELAY_FILE = "delays.json"
SESSION_FILE = "session.json"
SENT_FILE = "sent.json"

cl = Client()

# -------------------------
# SESSION FUNCTIONS
# -------------------------
def save_session():
    try:
        session = cl.get_settings()
        with open(SESSION_FILE, "w") as f:
            json.dump(session, f)
        print("✅ Session saved.")
    except Exception as e:
        print("❌ Session save error:", e)

def load_session():
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, "r") as f:
            session = json.load(f)
        cl.set_settings(session)
        cl.login(IG_USERNAME, IG_PASSWORD)
        print("✅ Logged in using saved session.")
        return True
    except Exception as e:
        print("❌ Session load/login error:", e)
        return False

def login_instagram():
    print("🔑 Logging in...")
    if not load_session():
        try:
            cl.login(IG_USERNAME, IG_PASSWORD)
            save_session()
        except Exception as e:
            print("❌ Instagram login failed:", e)
            raise e

# -------------------------
# MESSAGE FUNCTIONS
# -------------------------
def load_messages():
    if not os.path.exists(MESSAGES_FILE):
        return []
    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_delays():
    if not os.path.exists(DELAY_FILE):
        return [10]
    with open(DELAY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("delay_seconds_list", [10])

def load_sent():
    if not os.path.exists(SENT_FILE):
        return []
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_sent(sent_list):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent_list, f)

# -------------------------
# BOT LOOP
# -------------------------
def bot_loop():
    try:
        login_instagram()
    except Exception:
        print("🚨 Could not log in. Exiting bot loop.")
        return

    messages = load_messages()
    delays = load_delays()
    sent_messages = load_sent()

    if not messages:
        print("⚠️ No messages found. Add messages in messages.txt")
        return

    print(f"📨 Loaded {len(messages)} messages.")
    
    while True:
        for msg in messages:
            if msg in sent_messages:
                continue  # skip already sent messages

            delay = random.choice(delays)
            print(f"⏱ Waiting {delay} seconds before sending message...")
            time.sleep(delay)

            try:
                cl.direct_send(msg, [INSTAGRAM_THREAD_ID])
                print(f"✅ Sent: {msg}")
                sent_messages.append(msg)
                save_sent(sent_messages)
            except Exception as e:
                print("❌ Send error:", e)

# -------------------------
# FASTAPI SERVER
# -------------------------
app = FastAPI()

@app.get("/")
def home():
    return {"status": "Bot running"}

# -------------------------
# START BOT IN THREAD
# -------------------------
def start_bot():
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True
    thread.start()

# -------------------------
# ENTRY POINT
# -------------------------
if __name__ == "__main__":
    start_bot()
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
