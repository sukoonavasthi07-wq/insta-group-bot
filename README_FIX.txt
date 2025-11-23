# INSTAGRAM AUTO SENDER BOT (Render Deployment)

## 🔧 Files You Must Edit
Only edit:

config.py
---------
INSTAGRAM_USERNAME = "your_ig_username"
INSTAGRAM_PASSWORD = "your_ig_password"
INSTAGRAM_GROUP_ID = "your_instagram_group_thread_id"

messages.txt
------------
Write any messages you want to send automatically.
One message per line.

## 🚀 How It Works
1. app.py logs in to Instagram
2. Automatically creates session.json (no need to make it)
3. Loads messages from messages.txt
4. Sends them to your Instagram group forever
5. Random delays between messages: 10–60 seconds

## 🟣 Render Deployment

1. Upload all files:
   - app.py
   - config.py
   - messages.txt
   - requirements.txt
   - render.yaml

2. Render will install dependencies
3. Render will run:
   python app.py

Session.json will auto-generate on first login.

## 🔥 Notes
- Never delete session.json unless login fails.
- Make sure your Instagram credentials are correct.
- Use long delays to avoid restrictions.
