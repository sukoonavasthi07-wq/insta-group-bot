INSTAGRAM GROUP MESSAGE BOT — AUTO SESSION VERSION
====================================================

Now includes a HOME PAGE (/) to fix the "Not Found" error on Render.

----------------------------------------------------
HOME PAGE
----------------------------------------------------
Opening your Render URL will show:

Instagram Group Message Bot
Status: Running
Use POST /send to send messages.

----------------------------------------------------
API ROUTE
----------------------------------------------------
POST /send

BODY (JSON):
{
  "username": "...",
  "password": "...",
  "group_id": "...",
  "message": "...",
  "delay": 2,
  "cyclone_delay": 5
}

----------------------------------------------------
SESSION AUTO-LOGIN
----------------------------------------------------
• First run locally → approve login in Instagram app
• session.json gets created
• Upload session.json to GitHub
• Render auto-logs in with no challenge

----------------------------------------------------
FILES
----------------------------------------------------
app.py
render.yaml
requirements.txt
README_FIX.txt
session.json (after first run)

----------------------------------------------------
DONE!
----------------------------------------------------
