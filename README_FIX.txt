# Instagram Group Message Sender — README

This repo contains a Flask-based Instagram messaging bot that can send messages to group IDs with configurable delays and a cyclone delay. It supports session saving (`session.json`) to avoid repeated logins.

---

## Files

* `app.py` — main Flask app and bot logic (start/stop, queue, SSE logs)
* `render.yaml` — Render service configuration
* `requirements.txt` — Python dependencies
* `session.json` — (created/updated by the bot) stores instagrapi session settings

---

## Quickstart (local)

1. Create a virtualenv and activate it:

   ```bash
   python -m venv venv
   source venv/bin/activate  # on Windows: venv\\Scripts\\activate
   ```
2. Install requirements:

   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:

   ```bash
   python app.py
   ```
4. API endpoints:

   * `POST /start` — Start the bot (long-running background worker)
   * `POST /stop` — Stop the bot
   * `GET /status` — Bot status
   * `GET /logs` — Server-Sent Events (SSE) stream of live logs
   * `POST /send_once` — Queue a single send task (logs still available)

### /start body (JSON)

```json
{
  "username": "your_ig_username",
  "password": "your_ig_password",
  "group_ids": ["1234567890123456789"],
  "message": "Hello from bot",
  "delay": 3,
  "cyclone_delay": 10,
  "attachments": ["/path/to/image.jpg"],
  "cycles": 1
}
```

* `delay` is the normal wait (seconds) before each send
* `cyclone_delay` is additional wait after a send (seconds)
* `attachments` are local file paths on the server (optional)
* `cycles` is how many times to repeat the message(s)

---

## Notes & Safety

* Do **not** use this to spam. Instagram has strict rate limits and anti-abuse checks.
* The `session.json` is written to the project directory and contains auth settings — keep it private.
* For attachments: upload files to the server (e.g. to `/tmp/`) and provide their paths in the request body.

---

## Deploying to Render

1. Push the repo to GitHub.
2. Create a new Web Service on Render and connect the repo.
3. Render will use `render.yaml` to build and run the service.

---

## Troubleshooting

* If login fails, check credentials and look at `/logs` for details.
* If attachments fail, verify file paths and supported media types.

-- End of README --
