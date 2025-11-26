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

IG_USERNAME = "dracuhikehde"
IG_PASSWORD = "Dracu420"
INSTAGRAM_THREAD_ID = "788851167511644"

MESSAGES_FILE = "messages.txt"
DELAY_FILE = "delays.json"
SESSION_FILE = "session.json"

cl = Client()


# -------------------------
# SESSION FUNCTIONS
# -------------------------

def save_session():
    try:
        session = cl.get_session()
        with open(SESSION_FILE, "w") as f:
            json.dump(session, f)
        print("Session saved.")
    except Exception as e:
        print("Session save error:", e)


def load_session():
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, "r") as f:
            session = json.load(f)
        cl.set_session(session)
        cl.login(IG_USERNAME, IG_PASSWORD)
        print("Logged in using saved session.")
        return True
    except:
        return False


def login_instagram():
    print("Logging in...")
    if load_session():
        return
    cl.login(IG_USERNAME, IG_PASSWORD)
    save_session()


# -------------------------
# MESSAGE FUNCTIONS
# -------------------------

def load_messages():
    if not os.path.exists(MESSAGES_FILE):
        return []
    with open(MESSAGES_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def load_delays():
    if not os.path.exists(DELAY_FILE):
        return [10]
    with open(DELAY_FILE, "r") as f:
        return json.load(f)["delay_seconds_list"]


def bot_loop():
    login_instagram()

    messages = load_messages()
    delays = load_delays()

    print(f"Loaded {len(messages)} messages.")

    while True:
        for msg in messages:
            delay = random.choice(delays)
            print(f"Waiting {delay} seconds...")
            time.sleep(delay)
            try:
                cl.direct_send(msg, [INSTAGRAM_THREAD_ID])
                print("Sent:", msg)
            except Exception as e:
                print("Send error:", e)


# -------------------------
# FASTAPI SERVER (Required for FREE Render Web Service)
# -------------------------

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Bot running"}

def start_bot():
    thread = threading.Thread(target=bot_loop)
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    start_bot()
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
