# /nexum/server.py

"""
This script initializes and runs the HTTP server.
"""

import socketserver
import config
from api_handler import GameAPIHandler
from database import init_db

def run():
    """Initializes the database and starts the server."""
    # Ensure the database and tables exist before starting.
    init_db()

    # Allow the server address to be reused immediately
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    with socketserver.ThreadingTCPServer(("", config.API_PORT), GameAPIHandler) as httpd:
        print("--- GamePlex Server ---")
        print(f"Serving at: http://localhost:{config.API_PORT}")
        print(f"Static files served from: {config.STATIC_FILES_PATH}")
        print(f"Database editor available at: http://localhost:{config.API_PORT}/editor.html")
        print("Press Ctrl+C to stop the server.")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass # Allow clean shutdown on Ctrl+C
        
        httpd.server_close()
        print("\nServer stopped.")

