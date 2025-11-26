import json
import time
import random
from fastapi import FastAPI
from instagrapi import Client
from telegram.ext import Updater, MessageHandler, Filters
import config
import os

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Bot is running on Render"}

# Load delays from delays.json
def load_delays():
    with open("delays.json", "r") as f:
        return json.load(f)["delay_seconds_list"]

# persistent session directory
PERSIST_DIR = "/data"
os.makedirs(PERSIST_DIR, exist_ok=True)
SESSION_FILE = os.path.join(PERSIST_DIR, "insta_session.json")

cl = Client()

try:
    cl.load_settings(SESSION_FILE)
    cl.login(config.INSTAGRAM_USERNAME, config.INSTAGRAM_PASSWORD)
except:
    cl.login(config.INSTAGRAM_USERNAME, config.INSTAGRAM_PASSWORD)
    cl.dump_settings(SESSION_FILE)

def send_to_instagram(message):
    delays = load_delays()
    delay = random.choice(delays)
    time.sleep(delay)
    cl.direct_send(message, [config.INSTAGRAM_GROUP_ID])

def handle(update, context):
    text = update.message.text
    send_to_instagram(text)

updater = Updater(config.TELEGRAM_BOT_TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))
updater.start_polling()
