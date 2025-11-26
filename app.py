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

INSTAGRAM_THREAD_ID = "788851167511644"   # Put your thread ID

MESSAGES_FILE = "messages.txt"
DELAY_FILE = "delays.json"
SESSION_FILE = "session.json"


# -------------------------
# INSTAGRAM CLIENT
# -------------------------

cl = Client()


def save_session():
    """Save Instagram session after login"""
    try:
        session = cl.get_session()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f)
        print("Instagram session saved.")
    except Exception as e:
        print("Error saving session:", e)


def load_session():
    """Try loading saved IG session"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            cl.set_session(session_data)
            cl.login(IG_USERNAME, IG_PASSWORD)
            print("Logged in using saved session.")
            return True
        except Exception as e:
            print("Failed to load session:", e)
            return False
    return False


def login_instagram():
    print("Logging into Instagram...")

    if load_session():
        return

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        save_session()
        print("Instagram login successful.")
    except Exception as e:
        print("Instagram login failed:", e)


# -------------------------
# MESSAGE SENDING
# -------------------------

def load_delays():
    if os.path.exists(DELAY_FILE):
        try:
            with open(DELAY_FILE, "r") as f:
                return json.load(f)["delay_seconds_list"]
        except:
            pass
    return [10]  # fallback


def load_messages():
    """Read auto-messages from file"""
    if not os.path.exists(MESSAGES_FILE):
        return []

    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    # Remove empty lines
    return [msg for msg in lines if msg.strip()]


def auto_send_messages():
    """Send each message one-by-one from messages.txt"""
    messages = load_messages()
    delays = load_delays()

    print(f"Loaded {len(messages)} messages to auto-send.")

    for msg in messages:
        delay = random.choice(delays)
        print(f"\nWaiting {delay} seconds before sending next message...")
        time.sleep(delay)

        try:
            cl.direct_send(msg, [INSTAGRAM_THREAD_ID])
            print(f"Sent to Instagram: {msg}")
        except Exception as e:
            print("Failed to send message:", e)

    print("\nAll messages sent. Restart service to send again.")
    time.sleep(999999999)  # prevent Render from restarting loop


# -------------------------
# RUN
# -------------------------

if __name__ == "__main__":
    login_instagram()
    auto_send_messages()
