# /nexum/scanner.py

"""
Contains all logic for scanning the game library directory,
fetching metadata from the RAWG API, and populating the database.
"""

import os
import requests
import sqlite3
from urllib.parse import quote, unquote

import config
from database import get_db_connection, init_db

def _fetch_game_details(game_name):
    """Fetches detailed game information from the RAWG API."""
    print(f"Searching for '{game_name}' on RAWG...")
    if not config.RAWG_API_KEY or config.RAWG_API_KEY == "YOUR_RAWG_API_KEY":
        print("ERROR: RAWG_API_KEY is not configured in config.py.")
        return None
    try:
        search_url = f"https://api.rawg.io/api/games?key={config.RAWG_API_KEY}&search={unquote(game_name)}&page_size=1"
        response = requests.get(search_url, timeout=15)
        response.raise_for_status()
        search_results = response.json()
        if not search_results.get('results'):
            print(f"  > Game '{game_name}' not found on RAWG.")
            return None
        game_id = search_results['results'][0]['id']

        details_url = f"https://api.rawg.io/api/games/{game_id}?key={config.RAWG_API_KEY}"
        response = requests.get(details_url, timeout=15)
        response.raise_for_status()
        details = response.json()

        screenshots_url = f"https://api.rawg.io/api/games/{game_id}/screenshots?key={config.RAWG_API_KEY}"
        ss_response = requests.get(screenshots_url, timeout=15)
        ss_response.raise_for_status()
        details['screenshots_list'] = ss_response.json().get('results', [])

        print(f"  > Found: {details.get('name')}")
        return details
    except requests.exceptions.RequestException as e:
        print(f"  > ERROR: Could not connect to RAWG API. {e}")
        return None
    except (KeyError, IndexError) as e:
        print(f"  > ERROR: Unexpected response format from RAWG API. {e}")
        return None

def scan_library():
    """Scans the game library and populates the SQLite database."""
    init_db() # Ensure DB is ready
    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"Starting library scan in '{config.GAME_LIBRARY_PATH}'...")
    if not os.path.exists(config.GAME_LIBRARY_PATH):
        os.makedirs(config.GAME_LIBRARY_PATH)
        print(f"Created library directory. Add game folders and run scan again.")
        conn.close()
        return

    for game_folder in os.listdir(config.GAME_LIBRARY_PATH):
        # Check if the item is a directory
        if not os.path.isdir(os.path.join(config.GAME_LIBRARY_PATH, game_folder)):
            continue
            
        cursor.execute("SELECT id FROM games WHERE folder_name = ?", (game_folder,))
        if cursor.fetchone():
            print(f"Skipping '{game_folder}' (already in database).")
            continue

        print(f"\nProcessing new game: '{game_folder}'")
        details = _fetch_game_details(game_folder)
        if not details:
            continue

        artwork_dir = os.path.join(config.GAME_LIBRARY_PATH, game_folder, 'artwork')
        os.makedirs(artwork_dir, exist_ok=True)
        local_art_web_path = None
        art_url = details.get('background_image')
        if art_url:
            print(f"  > Caching poster artwork...")
            try:
                local_art_file = os.path.join(artwork_dir, 'poster.jpg')
                art_response = requests.get(art_url, stream=True, timeout=15)
                art_response.raise_for_status()
                with open(local_art_file, 'wb') as f:
                    for chunk in art_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                # Use a relative path for the web server
                local_art_web_path = f"/static/gamelibrary/{quote(game_folder)}/artwork/poster.jpg"
                print(f"  > Poster successfully cached.")
            except requests.exceptions.RequestException as e:
                print(f"  > WARNING: Could not download poster. {e}")

        cursor.execute('''
            INSERT INTO games (rawg_id, title, folder_name, developer, release_date, description, rating, art_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            details.get('id'), details.get('name'), game_folder,
            ", ".join([d['name'] for d in details.get('developers', [])]),
            details.get('released'), details.get('description_raw'), details.get('rating'),
            local_art_web_path
        ))
        game_db_id = cursor.lastrowid

        for genre_name in [g['name'] for g in details.get('genres', [])]:
            cursor.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (genre_name,))
            cursor.execute("SELECT id FROM genres WHERE name = ?", (genre_name,))
            genre_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO game_genres (game_id, genre_id) VALUES (?, ?)", (game_db_id, genre_id))

        screenshots_dir = os.path.join(artwork_dir, 'screenshots')
        os.makedirs(screenshots_dir, exist_ok=True)
        screenshots_to_fetch = details.get('screenshots_list', [])[:config.MAX_SCREENSHOTS]
        if screenshots_to_fetch:
            print(f"  > Caching {len(screenshots_to_fetch)} screenshots...")
            for i, ss in enumerate(screenshots_to_fetch):
                ss_url = ss.get('image')
                if not ss_url: continue
                try:
                    ss_filename = f"{i+1}.jpg"
                    ss_local_path = os.path.join(screenshots_dir, ss_filename)
                    ss_response = requests.get(ss_url, stream=True, timeout=15)
                    ss_response.raise_for_status()
                    with open(ss_local_path, 'wb') as f:
                        for chunk in ss_response.iter_content(chunk_size=8192): f.write(chunk)

                    ss_web_path = f"/static/gamelibrary/{quote(game_folder)}/artwork/screenshots/{ss_filename}"
                    cursor.execute("INSERT INTO screenshots (game_id, path) VALUES (?, ?)", (game_db_id, ss_web_path))
                except requests.exceptions.RequestException as e:
                    print(f"    - WARNING: Could not download screenshot {i+1}. {e}")
            print(f"  > Finished caching screenshots.")

        install_path = os.path.join(config.GAME_LIBRARY_PATH, game_folder, "install")
        if os.path.isdir(install_path):
            for filename in os.listdir(install_path):
                if os.path.isfile(os.path.join(install_path, filename)):
                    cursor.execute("INSERT INTO install_files (game_id, filename) VALUES (?, ?)", (game_db_id, filename))

        conn.commit()
        print(f"  > Successfully added '{details.get('name')}' to database.")

    conn.close()
    print("\nDatabase scan complete.")
