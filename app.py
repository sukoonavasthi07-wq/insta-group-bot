import threading
stop_event.clear()
bot_thread = threading.Thread(target=bot_worker, daemon=True)
bot_thread.start()


# Put credentials first so worker can login
task_queue.put({"username": username, "password": password})


# Then put the actual task
task_queue.put({
"group_ids": group_ids,
"message": message,
"delay": delay,
"cyclone_delay": cyclone_delay,
"attachments": attachments,
"cycles": cycles,
})


append_log("Start request accepted, task queued")
return jsonify({"status": "success", "message": "Bot started and task queued"})




@app.route('/stop', methods=['POST'])
def stop_bot():
stop_event.set()
append_log("Stop requested via API")
return jsonify({"status": "success", "message": "Stop requested"})




@app.route('/status', methods=['GET'])
def status():
running = bot_thread.is_alive() if bot_thread else False
return jsonify({"running": running, "queued_tasks": task_queue.qsize(), "log_count": len(logs)})




# SSE logs
@app.route('/logs')
def stream_logs():
def event_stream():
last_index = 0
while True:
with logs_lock:
new = logs[last_index:]
last_index = len(logs)
for entry in new:
yield f"data: {entry}\n\n"
time.sleep(1)
return Response(stream_with_context(event_stream()), mimetype='text/event-stream')




@app.route('/send_once', methods=['POST'])
def send_once():
data = request.json or {}
username = data.get('username')
password = data.get('password')
group_ids = data.get('group_ids') or []
message = data.get('message', '')
delay = data.get('delay', 3)
cyclone_delay = data.get('cyclone_delay', 0)
attachments = data.get('attachments', [])


if not username or not password or not group_ids:
return jsonify({"status": "error", "message": "username, password and group_ids are required"}), 400


# Queue credentials and single task
task_queue.put({"username": username, "password": password})
task_queue.put({
"group_ids": group_ids,
"message": message,
"delay": delay,
"cyclone_delay": cyclone_delay,
"attachments": attachments,
"cycles": 1,
})
append_log("One-time send queued")
return jsonify({"status": "success", "message": "Send queued"})




if __name__ == '__main__':
port = int(os.environ.get('PORT', 10000))
append_log(f"Starting Flask app on port {port}")
app.run(host='0.0.0.0', port=port, threaded=True)
