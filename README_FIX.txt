Instagram Group Message Sender Bot — Dark UI (Flask, Render)

Files:
 - app.py
 - render.yaml
 - requirements.txt
 - README_FIX.txt

Quick start:
1. Put these files in the root of a GitHub repo.
2. Connect the repo to Render (New -> Web Service -> GitHub).
3. Render will read render.yaml and run `pip install -r requirements.txt`.
4. The app will be available at https://<your-render-service>.onrender.com

Dashboard UI:
 - GET /          -> dashboard (dark theme)
 - POST /start    -> start the background bot (JSON payload)
 - POST /stop     -> stop the background bot
 - GET  /logs     -> live logs (SSE; used by UI)
 - POST /send_once -> send a single message (username/password required)

Start payload (JSON) for /start:
{
  "username": "your_ig_username",
  "password": "your_ig_password",
  "group_ids": ["1234567890123456789", "9876543210987654321"],
  "message": "Hello from the bot!",
  "attachment_url": "https://example.com/image.jpg",  # optional
  "delay": 3,
  "cyclone_delay": 8,
  "custom_name": "MyBot"
}

Notes & warnings:
 - Using username/password automation may trigger Instagram's security checks.
 - Avoid spamming; Instagram can ban accounts for automated abuse.
 - Test first with a throwaway account.
 - Attachments are fetched by the server from a provided URL (not file upload).
 - The bot uses a background thread; if the Render instance restarts the bot will stop and needs a manual start.

If you want:
 - file upload support (multipart) instead of URL-based attachments
 - persistent storage of credentials (NOT recommended)
 - token-based login (if you have it)
 - a React+build version for fancier UI

Use responsibly.
