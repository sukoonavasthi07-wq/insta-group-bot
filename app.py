import time
import random
from instagrapi import Client
from config import INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_GROUP_ID

cl = Client()

def instagram_login():
    try:
        print("Trying to load session.json...")
        cl.load_settings("session.json")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.get_timeline_feed()
        print("Logged in using session.json")
    except Exception as e:
        print("Session invalid or missing. Logging in fresh:", e)
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.dump_settings("session.json")
        print("New session.json auto-generated!")


def send_message_auto():
    # Load messages
    with open("messages.txt", "r", encoding="utf-8") as f:
        messages = [msg.strip() for msg in f.readlines() if msg.strip()]

    if not messages:
        print("messages.txt is EMPTY. Add messages first.")
        return

    print(f"Loaded {len(messages)} messages. Auto-sender started.\n")

    while True:
        msg = random.choice(messages)
        delay = random.choice([10, 20, 30, 40, 50, 60])

        print(f"Next message in {delay} seconds...")
        time.sleep(delay)

        try:
            cl.direct_send(msg, thread_ids=[INSTAGRAM_GROUP_ID])
            print(f"✓ Sent: {msg}")
        except Exception as e:
            print("❌ Sending error:", e)
            print("Waiting 60 seconds before retry...")
            time.sleep(60)


if __name__ == "__main__":
    instagram_login()
    send_message_auto()
