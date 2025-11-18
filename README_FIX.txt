==========================================================
 INSTAGRAM AUTO MESSAGE BOT – RENDER DEPLOYMENT GUIDE
==========================================================

This project allows you to send automatic Instagram messages
from a web UI hosted on Render. It supports:

✓ Multiple Instagram accounts (username + password)
✓ Automatic session.json creation / loading
✓ Sending messages to user IDs or group chat IDs
✓ Delays between messages
✓ Cyclone delays (big delay after a cycle)
✓ Selectable message input OR upload .txt message file
✓ Start Bot (Blue Button)
✓ Stop Bot (Red Button)
✓ 24/7 live logs on the same UI
✓ Render deployment (start command = python app.py)

----------------------------------------------------------
 REQUIRED FILES
----------------------------------------------------------
1. app.py            → Full Flask bot UI + backend
2. render.yaml       → Render service configuration
3. requirements.txt  → Python dependencies
4. README_FIX.txt    → (this file)
5. /templates/index.html (auto-created by app.py)
6. /sessions/        → Stores Instagram session.json files
7. /logs/            → Stores 24/7 bot logs

----------------------------------------------------------
 HOW TO USE THE WEB UI
----------------------------------------------------------

➤ STEP 1 — Add Instagram Accounts
---------------------------------
Inside the UI you will see:

Instagram Accounts:
----------------------------------------
Username: (type here)
Password: (type here)
[Add Account] button

You can add unlimited accounts.
Each account will generate:

  sessions/<username>.json

This happens automatically.

----------------------------------------------------------
 STEP 2 — Write Message or Upload Message File (.txt)
----------------------------------------------------------

You have two options:

1. Write your custom message in the message box

OR

2. Upload a text (.txt) file containing your message

Only one will be used.

----------------------------------------------------------
 STEP 3 — Add Target Usernames or Group Chat IDs
----------------------------------------------------------

You can enter:

✓ Instagram usernames  
✓ Group chat IDs (numeric thread IDs)

Example:

user1
user2
3498293849234   ← group thread id

----------------------------------------------------------
 STEP 4 — Set Delays
----------------------------------------------------------

Delay Between Messages (in seconds):
------------------------------------
Example: 8

Cyclone Delay (in seconds):
------------------------------------
Example: 120

Meaning:
- Delay = normal delay between each send  
- Cyclone delay = long delay after finishing all targets

----------------------------------------------------------
 STEP 5 — Start and Stop Buttons
----------------------------------------------------------

Two command buttons appear at the bottom:

[ BLUE  ]   Start Bot  
[  RED  ]   Stop Bot  

Once started, the bot runs in a background thread.

----------------------------------------------------------
 STEP 6 — Live Logs (24/7)
----------------------------------------------------------

At the bottom you will see:

----------------------------------------
Live Logs:
----------------------------------------
[Every sent message / error printed here]

Logs update continuously while bot is running.

----------------------------------------------------------
 DEPLOYMENT ON RENDER.COM
----------------------------------------------------------

1. Upload all project files to GitHub:
   - app.py
   - requirements.txt
   - render.yaml
   - README_FIX.txt
   - templates folder
   - logs folder
   - sessions folder

2. On Render:
   - Create "New Web Service"
   - Connect to your GitHub repo

3. Render automatically reads render.yaml

4. Start Command:
      python app.py

5. Bot will open on your render URL:
      https://your-app.onrender.com


----------------------------------------------------------
 AUTOMATIC SESSION.JSON HANDLING
----------------------------------------------------------

The bot automatically:

✓ Creates sessions/<username>.json for each account  
✓ Loads the session on next login  
✓ Recreates automatically if corrupted  

No manual steps required.

----------------------------------------------------------
 API USED
----------------------------------------------------------

instagrapi – Fast & stable private API  
Used for sending messages:
- Direct message to username
- Direct message to group thread id

----------------------------------------------------------
 WARNINGS
----------------------------------------------------------

⚠ Do NOT spam too fast.
⚠ Use cyclone delays to prevent Insta limits.
⚠ Use multiple accounts to spread workload.

----------------------------------------------------------
 ABOUT
----------------------------------------------------------

This UI was built using:
- Flask (Python)
- Instagrapi
- HTML / AJAX
- Render background threading system

==========================================================
 END OF README_FIX.txt
==========================================================
