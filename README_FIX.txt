# Instagram Group Message Sender Bot (Render Deployment)

This bot allows you to log in using Instagram username + password and send
messages to Instagram group IDs with normal and cyclone delays.

===========================================
UI STRUCTURE (FOR FRONT-END DEVELOPERS)
===========================================

1. LOGIN SECTION
----------------
• Username
• Password

2. MESSAGE SENDER
-----------------
• Message input box
• File upload (image/video/document)

3. CUSTOM SENDER INFO
---------------------
• Custom display name

4. GROUP ID SECTION
-------------------
• Input field for Instagram group ID

5. DELAY CONTROLS
-----------------
• Normal delay (seconds)
• Cyclone delay (seconds)

6. BOT CONTROL
--------------
• Start Bot (Blue Button)
• Stop Bot (Red Button)

7. LIVE LOGS (24×7)
-------------------
Shows:
• Sent messages
• Timestamps
• Errors
• Delay countdown
• Bot status

===========================================
API USAGE
===========================================

POST https://your-render-url.onrender.com/send

JSON BODY:
{
  "username": "your_ig_username",
  "password": "your_ig_password",
  "group_id": "123456789",
  "message": "Hello!",
  "delay": 3,
  "cyclone_delay": 8
}

===========================================
FILE STRUCTURE
===========================================
/app.py
/render.yaml
/requirements.txt
/README_FIX.txt

===========================================
DEPLOYING ON RENDER
===========================================

1. Upload all files to GitHub.
2. Create new Web Service on Render.
3. Render reads render.yaml automatically.
4. Deploy and use API.

===========================================
DONE!
===========================================
