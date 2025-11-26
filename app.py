import os
import time
import json
import random
from telegram.ext import Updater, MessageHandler, Filters
from instagrapi import Client

# -------------------------
# CONFIG
# -------------------------
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

IG_USERNAME = "your_instagram_username"
IG_PASSWORD = "your_instagram_password"

# Instagram DM Thread ID (user, group, broadcast)
INSTAGRAM_THREAD_ID = "12345678901234567"

DELAY_FILE = "delays.json"
SESSION_FILE = "session.json"

# -------------------------
# INSTAGRAM LOGIN + SESSION
# -------------------------

cl = Client()


def save_session():
    """Save Instagram session to session.json"""
    try:
        session = cl.get_session()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f)
        print("Instagram session saved.")
    except Exception as e:
        print("Error saving session:", e)


def load_session():
    """Load Instagram session if exists"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            cl.set_session(session_data)
            cl.login(IG_USERNAME, IG_PASSWORD)
            print("Logged in using saved session.")
            return True
        except Exception as e:
            print("Saved session failed:", e)
            return False
    return False


def login_instagram():
    """Login automatically using saved session or normal login"""
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
    return [3, 5, 8]  # default delays


def send_instagram_message(msg):
    delays = load_delays()
    delay = random.choice(delays)
    print(f"Delay before sending: {delay} seconds")

    time.sleep(delay)

    try:
        cl.direct_send(msg, [INSTAGRAM_THREAD_ID])
        print("Sent to Instagram:", msg)
    except Exception as e:
        print("Failed to send message:", e)


# -------------------------
# TELEGRAM BOT
# -------------------------

def tg_handler(update, context):
    text = update.message.text
    print("Telegram message received:", text)
    send_instagram_message(text)


def start_telegram_bot():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, tg_handler))

    print("Telegram bot is running...")
    updater.start_polling()
    updater.idle()


# -------------------------
# RUN BOT
# -------------------------

if __name__ == "__main__":
    login_instagram()
    start_telegram_bot()
