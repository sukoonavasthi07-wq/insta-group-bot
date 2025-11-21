# README_FIX.txt (Updated Version)

## 📌 Instagram Group Message Bot — Complete Guide
This README provides full instructions for using the **Real-Mode Instagram Group Messaging Bot** with full support for:
- Dark / Neon / Glassmorphism UI
- Multi-account login
- Session.json auto-generation
- Message rotation
- Cyclone delays
- Real-time logs (SSE)
- Render deployment

---

## ✅ 1. Login Details
Enter **Instagram Username** and **Password**.
- Password is **never stored**.
- Session settings are saved to:
```
sessions/<username>_session.json
```

If Instagram triggers 2FA/checkpoint, login once manually on mobile, then restart bot.

---

## ✅ 2. Message Input
You may:
### A) Type message manually
### B) Upload `.txt` file containing multiple messages
- If the uploaded file contains multiple lines, the bot will **rotate messages**.

---

## ✅ 3. Group Thread IDs
Enter Instagram **group chat IDs** (one per line):
```
34028236684171030094836434756xxxxxx
34028236684171030094912817356xxxxxx
```
Bot will send messages sequentially to each ID.

---

## ✅ 4. Delays & Cyclone Pattern
### Base Delay
Delay between messages in seconds.

### Cyclone Delay Range
Bot applies a random delay:
```
random(min_cyclone, max_cyclone)
```
This prevents detection and rate-limit blocks.

---

## ✅ 5. Multi-Account Support
You can add multiple accounts by entering different login credentials.
Each account will have a unique session stored.

The bot switches accounts automatically.

---

## ✅ 6. Start / Stop Bot
### 🔵 START BOT
- Logs in account
- Creates session.json if not present
- Loads all message rules
- Starts background worker thread
- Applies base/cyclone delays
- Shows real-time logs

### 🔴 STOP BOT
- Stops message loop immediately
- Thread safe
- UI updates instantly

---

## ✅ 7. Live Logs (Real Time)
The UI shows:
- Login events
- Session load success/failures
- Message send success
- Errors & retries
- Delay timers
- Stops & restarts

Logs are streamed via **SSE**.

---

## 🎨 8. UI Theme (Dark + Neon + Glassmorphism)
The UI uses:
- Deep dark background
- Neon blue & neon green glow
- Frosted glass cards
- Smooth rounded edges (16–25px)
- Animated hover effects

If you want theme presets, ask: **"Add theme presets"**

---

## 🚀 9. Render Deployment
Use the included `render.yaml` file.
Build command:
```
pip install -r requirements.txt
```
Start command:
```
python app.py
```
Render will expose the web UI.

---

## 📁 10. Project Files
```
app.py
requirements.txt
render.yaml
README_FIX.txt
sessions/ <auto created>
```

---

## ⚠️ 11. Important Notes
- Use responsibly; Instagram blocks spam.
- Avoid messaging too fast.
- Expect occasional rate limits.
- 2FA / checkpoint must be resolved manually once.

---

## 🎉 Finished!
Your bot is now fully functional and documented.
If you want ZIP packaging or theme presets, just say the word!
