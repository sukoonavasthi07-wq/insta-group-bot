import time
import random
from instagrapi import Client
from config import INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_GROUP_ID

cl = Client()


def instagram_login():
    print("Attempting session load...")

    try:
        cl.load_settings("session.json")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.get_timeline_feed()
        print("Session loaded successfully.")
    except Exception as e:
        print("Session missing or invalid. Logging in fresh:", e)
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.dump_settings("session.json")
        print("New session.json created.")


def auto_sender():
    # Load messages from file
    try:
        with open("messages.txt", "r", encoding="utf-8") as f:
            messages = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print("messages.txt NOT FOUND — create the file first!")
        return

    if not messages:
        print("messages.txt is empty — add some lines!")
        return

    print(f"Loaded {len(messages)} messages. Starting auto-poster...")

    while True:
        msg = random.choice(messages)

        delay = random.choice([10, 20, 30, 40, 50, 60])
        print(f"\nWaiting {delay} seconds before next message...")
        time.sleep(delay)

        try:
            cl.direct_send(msg, thread_ids=[INSTAGRAM_GROUP_ID])
            print(f"Sent message: {msg}")
        except Exception as e:
            print("Send error:", e)
            print("Sleeping 60 seconds, retrying...")
            time.sleep(60)


if __name__ == "__main__":
    instagram_login()
    auto_sender()
