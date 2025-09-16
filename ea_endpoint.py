from flask import Flask, request, jsonify
import threading
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Your Flask route example
@app.route("/ea-status-update", methods=["POST"])
def ea_status_update():
    data = request.json
    # Process the update here
    logging.info(f"Received update: {data}")
    return jsonify({"status": "ok"}), 200

def run_flask():
    # Listen on all interfaces, port 5000 - adjust as needed
    app.run(host="0.0.0.0", port=5000)

# Call this once at signalworker startup to run Flask server in background
def start_flask_in_thread():
    thread = threading.Thread(target=run_flask)
    thread.daemon = True  # Daemon thread will not block shutdown
    thread.start()

if __name__ == "__main__":
    start_flask_in_thread()
    # Your main signalworker logic continues here

    while True:
        # main loop processing signals
        pass