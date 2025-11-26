import os
import time
import json
import random
from instagrapi import Client

# -------------------------
# CONFIG
# -------------------------
IG_USERNAME = "dracuhikehde"
IG_PASSWORD = "Dracu420"

INSTAGRAM_THREAD_ID = "788851167511644"  # Replace with your real thread ID

MESSAGES_FILE = "messages.txt"
DELAY_FILE = "delays.json"
SESSION_FILE = "session.json"

cl = Client()


# -------------------------
# SESSION HANDLING
# -------------------------

def save_session():
    """Save session to file"""
    try:
        session = cl.get_session()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f)
        print("Instagram session saved.")
    except Exception as e:
        print("Failed to save session:", e)


def load_session():
    """Try loading an existing session"""
    if not os.path.exists(SESSION_FILE):
        return False

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session = json.load(f)

        cl.set_session(session)
        cl.login(IG_USERNAME, IG_PASSWORD)
        print("Logged in using saved session.")
        return True

    except Exception as e:
        print("Saved session failed:", e)
        return False


def login_instagram():
    """Login using session or fresh login"""
    print("Logging into Instagram...")

    if load_session():
        return

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        save_session()
        print("Instagram login successful.")
    except Exception as e:
        print("LOGIN FAILED:", e)


# -------------------------
# MESSAGE FUNCTIONS
# -------------------------

def load_messages():
    """Load message list from file"""
    if not os.path.exists(MESSAGES_FILE):
        print("messages.txt not found!")
        return []

    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        lines = [msg.strip() for msg in f.readlines() if msg.strip()]

    return lines


def load_delays():
    """Load delay list"""
    if not os.path.exists(DELAY_FILE):
        return [5]  # default fallback

    with open(DELAY_FILE, "r") as f:
        return json.load(f)["delay_seconds_list"]


def auto_send_messages():
    """Send each message one by one"""
    messages = load_messages()
    delays = load_delays()

    print(f"Total messages to send: {len(messages)}")

    for msg in messages:
        delay = random.choice(delays)
        print(f"\nWaiting {delay} seconds...")
        time.sleep(delay)

        try:
            cl.direct_send(msg, [INSTAGRAM_THREAD_ID])
            print(f"SENT TO INSTAGRAM: {msg}")
        except Exception as e:
            print("FAILED:", e)

    print("\nAll messages sent. Sleeping forever...")
    while True:
        time.sleep(999999)
