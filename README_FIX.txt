Instagram Group Message Sender — Full Start/Stop Bot (Option B)


Files:
- app.py
- render.yaml
- requirements.txt
- session.json (optional; created automatically at /tmp/session.json)


Quickstart (local):
1. python -m venv venv
2. source venv/bin/activate # Windows: venv\Scripts\activate
3. pip install -r requirements.txt
4. python app.py


API endpoints:
- POST /start -> start the bot and queue a repeating task
- POST /stop -> stop the bot
- GET /status -> get running state
- GET /logs -> SSE stream of logs
- POST /send_once -> queue a single send


/start body example:
{
"username": "your_ig_username",
"password": "your_ig_password",
"group_ids": ["1234567890123456789"],
"message": "Hello from bot",
"delay": 3,
"cyclone_delay": 10,
"attachments": ["/tmp/myphoto.jpg"],
"cycles": 5
}


Notes:
- session.json is stored in /tmp by default on Render; this is ephemeral but writable.
- Attachments must be present on disk in the server environment (or implement upload endpoint).
- Do not spam — test with a throwaway account.
