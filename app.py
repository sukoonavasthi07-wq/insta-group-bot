from flask import Flask, request, jsonify
from instagrapi import Client
import os, json, time

app = Flask(__name__)

# ---------------------------
# Auto-login with Session.json
# ---------------------------
def login_to_instagram(username, password):
    cl = Client()

    # If session exists, try auto-login
    if os.path.exists("session.json"):
        try:
            settings = json.load(open("session.json"))
            cl.set_settings(settings)
            
            cl.login(username, password)
            print("[AUTO-LOGIN] Logged in using saved session.json")
            return cl
        except Exception as e:
            print("[AUTO-LOGIN FAILED]", e)
            print("[INFO] Trying fresh login...")

    # Fresh login (first time)
    cl = Client()
    cl.login(username, password)

    # Save session
    with open("session.json", "w") as f:
        json.dump(cl.get_settings(), f)

    print("[NEW LOGIN] Session saved to session.json")
    return cl


# ---------------------------
# Send message to group ID
# ---------------------------
def send_message_with_delays(cl, group_id, message, delay, cyclone_delay):
    time.sleep(delay)
    time.sleep(cyclone_delay)
    cl.direct_send(message, [group_id])


@app.route("/send", methods=["POST"])
def send_message():
    data = request.json

    username = data.get("username")
    password = data.get("password")
    group_id = data.get("group_id")
    message = data.get("message")
    delay = float(data.get("delay", 2))
    cyclone_delay = float(data.get("cyclone_delay", 5))

    try:
        cl = login_to_instagram(username, password)
        send_message_with_delays(cl, group_id, message, delay, cyclone_delay)

        return jsonify({"status": "success", "message": "Message sent!"})

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
