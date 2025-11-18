INSTAGRAM GROUP MESSAGE BOT — AUTO SESSION VERSION
====================================================

This bot logs into Instagram using a saved session.json
so it NEVER asks for verification after the first login.

----------------------------------------------------
HOW TO USE
----------------------------------------------------

STEP 1 — Run the bot ONCE on your local computer:
   python app.py

STEP 2 — Login with your Instagram account.
Instagram will ask for approval the FIRST TIME only.

STEP 3 — Approve the login in Instagram app:
   Security > Login Activity > "This Was Me"

STEP 4 — session.json will be created automatically.

STEP 5 — Upload session.json to GitHub along with:
   app.py
   requirements.txt
   render.yaml
   README_FIX.txt

STEP 6 — Deploy to Render → Works automatically.

----------------------------------------------------
API USAGE
----------------------------------------------------

POST https://your-render-url.onrender.com/send

BODY (JSON):
{
  "username": "your_ig_username",
  "password": "your_ig_password",
  "message": "Hello!",
  "group_id": "123456789",
  "delay": 2,
  "cyclone_delay": 5
}

----------------------------------------------------
FEATURES
----------------------------------------------------

• Auto-login using saved session.json
• No Instagram challenge after first approval
• Supports group ID messaging
• Delay + cyclone delay supported
• Ready for Render deployment
• Very stable for 24×7 automation

----------------------------------------------------
DONE!
----------------------------------------------------
