# README_FIX.txt

## Instagram Group Message Bot (Render + Flask + Instagrapi)

### Fully Working: Login → Auto Session.json → Start/Stop Bot → Live Logs → Delays + Cyclone

---

## 1. LOGIN DETAILS (Required)

Enter your **Instagram Username** and **Instagram Password**.

* Automatically creates `/sessions/session.json`.
* Reuses the same session every time.
* Password is NOT saved to disk.

---

## 2. WRITE MESSAGE OR UPLOAD TXT

You may:

* Type a custom message manually, **or**
* Upload a `.txt` file containing the message.

---

## 3. CUSTOM NAME OR USERNAME (Optional)

Write a custom name or Instagram username for identifying logs. (Not used for sending.)

---

## 4. GROUP CHAT IDs (Required)

Add Instagram **Group Thread IDs**, one per line.
Example:

```
340282366841710300949128173567xxxxxxx
340282366841710300948232347567xxxxxxx
```

---

## 5. DELAYS BETWEEN MESSAGES

Add base delay (seconds), e.g.:

```
8
```

This delay is applied between each message.

---

## 6. CYCLONE DELAYS (Randomized Delays)

Add random delay range:

```
Min: 3
Max: 12
```

Bot uses `random(min, max)` before sends.

---

## 7. START / STOP BOT

### 🔵 START BOT

* Logs into Instagram
* Loads/creates session.json
* Begins messaging loop
* Applies delays
* Shows live logs
* Runs 24/7 until stopped

### 🔴 STOP BOT

* Graceful shutdown
* Halts message sending immediately

---

## 8. LIVE LOGS

Live logs include:

* Message sent status
* Failures & retries
* Cyclone delay usage
* Session creation logs
* Start/stop notifications

Logs stream in real time using SSE.

---

## 9. RUNNING THE BOT

Start the app:

```
python app.py
```

Deploy to Render using `render.yaml`. The web UI loads automatically.

---

## 10. FILES INCLUDED

```
app.py
README_FIX.txt
requirements.txt
yaml (render.yaml)
sessions/session.json (auto)
```

---

## 11. IMPORTANT NOTE

If Instagram asks for 2FA or checkpoint, complete it manually on mobile. After that, the bot will continue using `session.json`.
