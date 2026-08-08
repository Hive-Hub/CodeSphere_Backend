import eventlet
eventlet.monkey_patch()

import os

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_ENV", "development") == "development"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode)
