# Instagram Group Message Bot (Render Deployment)

This project lets you send automated Instagram group messages using a Flask backend + Instagrapi bot + web UI. Designed to run on **Render** with GitHub deployment.

---

## 📌 FEATURES

* Login using **Instagram username + password**
* Automatically load and save **session.json** for login approval bypass
* Send message to multiple group IDs
* Delay between messages + cyclone delay
* Live logs (real‑time)
* Start Bot / Stop Bot buttons
* Manual "Send Once" option
* Uses SSE (Server‑Sent Events) for stable logging on Render

---

## 📁 PROJECT STRUCTURE

```
app.py
requirements.txt
render.yaml
README_FIX.txt
/templates
    index.html
/static
    style.css
    app.js
session.json (auto-created after first login)
```

---

## 🔑 LOGIN SYSTEM (IMPORTANT)

1. Enter **Instagram username and password** in the UI.
2. If Instagram sends a *“Was this you?”* alert:

   * Open Instagram → Settings → Login Activity → Approve “Yes, it was me”.
3. Run bot again → `session.json` will be saved → **Auto-login works next time**.

⚠️ The bot does **NOT** support 2FA. Disable 2FA or use an alt account.

---

## 📨 MESSAGE INPUT SYSTEM

UI gives you:

* **Message box** → Write text message only (no image upload).
* **Custom Sender Name** (optional)
* **Group IDs box** → Enter 1 or more Instagram thread IDs (comma-separated).

Example:

```
340282366841710300949128123456789012345
340282366841710300112233445566778899001
```

✔️ The bot sends messages to each group in cycles.

---

## ⏱ DELAY SYSTEM

You can set:

* **Delay (seconds)** → Normal delay before each send
* **Cyclone Delay (seconds)** → Extra random delay each cycle

Bot calculates small random variations to avoid spam detection.

---

## ▶️ STARTING THE BOT

Click **Start Bot (blue button)**.

Bot begins sending messages according to:

* Message
* Group IDs
* Delay values

Live logs appear at the bottom in real time.

---

## ⏹ STOPPING THE BOT

Click **Stop Bot (red button)**.

Bot safely stops at the next delay checkpoint.

---

## 🖥 HOW TO DEPLOY ON RENDER

### 1️⃣ Push files to GitHub

Make sure your repo contains:

```
app.py
requirements.txt
render.yaml
/templates
/static
```

### 2️⃣ Go to [https://render.com](https://render.com) → New Web Service

* Connect GitHub Repository
* Render auto-detects **render.yaml**
* Click *Deploy*

Render builds and runs the bot using:

```
gunicorn app:app
```

---

## 📡 LIVE LOGS

Open `/logs` endpoint OR view logs inside the UI.
Works through SSE — stable on Render.

---

## ❗ IMPORTANT NOTES

* Use a **secondary Instagram account** to avoid restrictions.
* Avoid sending too fast → can lock your account.
* Do NOT use VPN inside Render.
* Render free dynos sleep after inactivity.

---

## ✔️ READY TO USE

Once deployed:

* Open the web URL
* Login
* Enter message + group IDs
* Click **Start Bot**
* Watch messages send automatically

---

If you want, I can also generate:

* `/templates/index.html`
* `/static/style.css`
* `/static/app.js`

Just tell me: **"Create UI files"**
