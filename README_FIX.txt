# Instagram ↔ Telegram Bot (Render Deployment)

## Steps:
1. Create a new Web Service on Render.
2. Connect GitHub repo.
3. Build command:
   pip install -r requirements.txt
4. Start command:
   uvicorn main:app --host 0.0.0.0 --port $PORT
