from flask import Flask, request, jsonify
import time
import random
import os
from instagrapi import Client

app = Flask(__name__)

# Login handler
def login_to_instagram(username, password):
    client = Client()
    client.login(username, password)
    return client

# Send message + delays
def send_message_with_delays(client, group_id, message, delay, cyclone_delay):
    time.sleep(delay)
    time.sleep(cyclone_delay)
    client.direct_send(message, [group_id])

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json

    username = data.get("username")
    password = data.get("password")
    group_id = data.get("group_id")
    message = data.get("message")
    delay = float(data.get("delay", 3))
    cyclone_delay = float(data.get("cyclone_delay", 8))

    try:
        client = login_to_instagram(username, password)
        send_message_with_delays(client, group_id, message, delay, cyclone_delay)

        return jsonify({"status": "success", "message": "Message sent successfully!"})

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
