===========================================================
              INSTAGRAM AUTO DM BOT (RENDER UI)
===========================================================

This project runs an automated Instagram DM Sender inside 
a Flask web interface deployed on Render.

Everything is controlled through the web page:
✔ Multiple Instagram Accounts
✔ Message Writing / Upload messages.txt file
✔ Custom Name
✔ Usernames & Group Chat IDs
✔ Normal Delays
✔ Cyclone Delays
✔ Blue "Start Bot" Button
✔ Red "Stop Bot" Button
✔ Live Logs (Auto-refresh 24/7)
✔ Automatic session.json generation

The Render dashboard provides direct control over the bot.

===========================================================
1) MULTIPLE INSTAGRAM ACCOUNTS
===========================================================

Inside the web interface, you will see fields like:

-------------------------------------
Account 1 Username:  ____________
Account 1 Password:  ____________

Account 2 Username:  ____________
Account 2 Password:  ____________

Account 3 Username:  ____________
Account 3 Password:  ____________
-------------------------------------

You can add unlimited accounts in the UI.

The bot auto-switches when:
• Rate-limited
• Temporarily blocked
• Challenge required

===========================================================
2) MESSAGE INPUT (TEXTBOX OR TXT UPLOAD)
===========================================================

On the UI, you will have:

-------------------------------------
[ Write Message Here ]
-------------------------------------

Or you can upload:
-------------------------------------
messages.txt
-------------------------------------

Format for messages.txt:
Each line = one message

Example:
Hello!
This is your IG automation bot.
Hope you are having a good day.

Bot automatically cycles messages.

===========================================================
3) CUSTOM NAME
===========================================================

UI Field:
-------------------------------------
Custom Name:  ____________
-------------------------------------

Used like:
"Hello <CustomName>, how are you?"

===========================================================
4) TARGET USERS & GROUP CHAT IDs
===========================================================

Two sections in UI:

A) For usernames:
-------------------------------------
Target Usernames:
user1,user2,user3
-------------------------------------

B) For group chats:
-------------------------------------
Group Chat IDs:
1234567890,4455667788,9988771122
-------------------------------------

The bot sends DMs to:
✓ individual profiles  
✓ group chat threads  

===========================================================
5) DELAYS BETWEEN MESSAGES (NORMAL DELAY)
===========================================================

UI Input Fields:
-------------------------------------
Min Delay (seconds): ____
Max Delay (seconds): ____
-------------------------------------

Bot waits between these values.

===========================================================
6) CYCLONE DELAYS (ADVANCED CYCLIC DELAY)
===========================================================

UI Fields:
-------------------------------------
Cyclone Pattern: 2,5,10,4
Cyclone Jitter:  0.25
-------------------------------------

Meaning:
Send → wait 2s  
Send → wait 5s  
Send → wait 10s  
Send → wait 4s  
Repeats forever.

Jitter = ±25% randomization.

===========================================================
7) CONTROL BUTTONS (RENDER UI)
===========================================================

Two buttons appear directly inside the Flask web page:

-------------------------------------
[ 🔵 START BOT ]
Starts sending messages 24/7
Route: /start

[ 🔴 STOP BOT ]
Stops the bot immediately
Route: /stop
-------------------------------------

Bot status displays below these buttons.

===========================================================
8) LIVE LOGS (AUTOMATICALLY REFRESHING)
===========================================================

At bottom of the page you will see:

-------------------------------------
📌 Live Logs (auto-refresh every 2 seconds)
-------------------------------------

It displays:

• Current account  
• Message sent  
• User / Group ID  
• Delay applied  
• Errors & retries  
• Account switching  
• Session restore  
• Login challenge and handling  

Logs also write to:
-------------------------------------
logs/live.log
-------------------------------------

===========================================================
9) AUTO SESSION MANAGEMENT
===========================================================

Bot automatically creates and updates:
-------------------------------------
session.json
-------------------------------------

This file stores:
• Cookies  
• Login tokens  
• Device ID  

Purpose:
✓ Prevents login every time  
✓ Avoids checkpoints  
✓ Reduces risk of blocking  

===========================================================
10) HOW TO DEPLOY ON RENDER
===========================================================

1. Upload files:
- app.py
- render.yaml
- requirements.txt
- README_FIX.txt

2. Push to GitHub

3. Connect repository to Render

4. Render automatically deploys Flask app

5. Open "Public URL"

You will see:
✓ Inputs  
✓ Buttons  
✓ Logs  
✓ Controls  

Bot runs fully online 24/7.

===========================================================
11) SAFETY NOTES
===========================================================

• Do not abuse message sending  
• Avoid spamming  
• Use multiple accounts wisely  
• Respect Instagram limits  

===========================================================
END OF README
===========================================================
