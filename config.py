# /nexum/config.py

"""
Central configuration file for the Nexum server.
All constants and configuration variables should be defined here.
"""

import os

# --- API Keys ---
# It's recommended to load this from an environment variable for better security.
# For example: RAWG_API_KEY = os.getenv("RAWG_API_KEY", "YOUR_DEFAULT_KEY")
RAWG_API_KEY = "06326ce3913d46c0a4dd963b64c09221"

# --- Paths ---
# Use absolute paths to avoid issues when running the script from different directories.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GAME_LIBRARY_PATH = os.path.join(PROJECT_ROOT, "gamelibrary")
DATABASE_PATH = os.path.join(PROJECT_ROOT, "gameplex.db")
SAVES_STORAGE_PATH = os.path.join(PROJECT_ROOT, "saves")
STATIC_FILES_PATH = os.path.join(PROJECT_ROOT, "static")


# --- Server Settings ---
API_PORT = 8000

# --- Scanner Settings ---
MAX_SCREENSHOTS = 6

# --- Cloud Saves ---
SAVES_LIMIT = 6 # The number of rotating saves to keep per game
