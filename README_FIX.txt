INSTAGRAM AUTO DM BOT - README

Files:
- app.py           : Flask app and DM sender logic (server + runner).
- requirements.txt : Python deps.
- render.yaml      : Example Render service definition.
- sessions/        : auto-created folder containing per-account session files (do not commit).
- logs/live.log    : appended logs (auto-created).
- Ui Dashboard     : frontend HTML file already created in the project (ui_dashboard.html).

SUMMARY
This service can:
- Use multiple Instagram accounts (round-robin)
- Read messages (list or uploaded .txt -> one message per line)
- Send to recipients (usernames or numeric group thread IDs)
- Support static min/max delays and a 'cyclone' pattern with jitter
- Retry with exponential backoff
- Auto-create session files per account (sessions/<username>_session.json)
- Start / Stop via API and UI
- Live logs stored to logs/live.log and available via /logs

QUICK USAGE
1) Deploy to Render with render.yaml, or run locally:
   pip install -r requirements.txt
   python app.py

2) Provide either:
   - JSON POST to /send with a config (see below), or
   - Set env vars INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD and POST /send with messages & recipients.

3) Example POST payload (JSON):
{
  "accounts": [
    {"username": "acct1", "password": "pass1"},
    {"username": "acct2", "password": "pass2"}
  ],
  "messages": ["Hello {name}", "Quick update for you."],
  "recipients": ["targetuser1", "123456789012345"],   # numeric looks like group id
  "custom_name": "Alex",
  "min_delay": 3,
  "max_delay": 6,
  "cyclone_pattern": [2,5,10,4],
  "cyclone_jitter": 0.25,
  "max_retries": 4,
  "base_backoff": 2.0,
  "singleRun": false
}

4) Endpoints:
- POST /send   -> start job (accepts config JSON). Use "testOnly": true to test logins.
- POST /stop   -> stop job
- GET  /status -> returns status JSON
- GET  /logs   -> returns recent logs (plain text). ?full=1 returns full file for download.

UI
The provided `ui_dashboard.html` interacts with these endpoints (POST /send, POST /stop, GET /status, GET /logs). Place the HTML in the same deployment or serve it from Render static / another hosting.

SAFETY & NOTES
- Use only with accounts you own or have permission to message.
- Instagram may challenge/log you out for suspicious activity (2FA). If a login challenge occurs, the runner may fail to log in — check logs to resolve.
- Respect rate limits and anti-spam rules. Use low send rates and multiple accounts as needed.
- Do NOT commit sessions/credentials to git.

