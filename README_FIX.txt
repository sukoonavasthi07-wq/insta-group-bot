INSTAGRAM DM SENDER - README

API
POST /send    -> start job (JSON config). Required: messages, recipients. Optionally accounts.
POST /stop    -> stop job
GET  /status  -> status json
GET  /logs    -> logs (plain text)  (use ?full=1 to download full file)

Files / folders
- app.py          : Flask backend (this file)
- requirements.txt: dependencies
- render.yaml     : sample Render config
- sessions/       : session files auto-created here (per-account). DO NOT COMMIT.
- logs/live.log   : appended logs (auto-created)

Sessions
- For each account the runner will create/update:
  sessions/<username>_session.json
- These session files persist login state and are auto-written after login/send.
- If a session exists it will attempt to reuse it.

Quick JSON example to POST /send:
{
  "accounts": [{"username":"acct1","password":"pass1"}, {"username":"acct2","password":"pass2"}],
  "messages": ["Hello {name}", "Quick update for you."],
  "recipients": ["targetuser1","123456789012345"],
  "custom_name": "Alex",
  "min_delay": 3,
  "max_delay": 6,
  "cyclone_pattern": [2,5,10,4],
  "cyclone_jitter": 0.25,
  "max_retries": 4,
  "base_backoff": 2.0,
  "singleRun": true
}

Notes
- Use only for accounts you own or have permission to message.
- Instagram can challenge logins (2FA). If login challenge occurs, manual intervention may be required.
- Respect rate limits and avoid spammy behavior.

