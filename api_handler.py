# /gameplex_project/api_handler.py

"""
The main request handler for the GamePlex API.
Inherits from SimpleHTTPRequestHandler to serve static files
and adds custom logic for API endpoints.
"""

import http.server
import json
import os
import re
import shutil
import sqlite3
import time
import requests
from email.parser import BytesParser
from urllib.parse import urlparse, parse_qs, quote

import config
import scanner
from database import get_db_connection
from scanner import _fetch_game_details

class GameAPIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve files from the 'static' directory by default
        super().__init__(*args, directory=config.STATIC_FILES_PATH, **kwargs)

    def _rawg_api_request(self, url):
        """Helper function to make requests to the RAWG API."""
        if not config.RAWG_API_KEY or config.RAWG_API_KEY == "YOUR_RAWG_API_KEY":
            self.send_error(500, "RAWG API Key is not configured on the server.")
            return None
        try:
            full_url = f"{url}&key={config.RAWG_API_KEY}"
            response = requests.get(full_url, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.send_error(503, f"Could not connect to RAWG API: {e}")
            return None

    # --- ROUTING (do_GET, do_POST, etc.) ---
    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-type")
        self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path.rstrip('/')
        path_parts = path.strip("/").split("/")

        if path.startswith('/api/'):
            try:
                if path == '/api/search/rawg':
                    query = parse_qs(parsed_path.query).get('query', [''])[0]
                    if not query: return self.send_error(400, "Missing search query.")
                    search_url = f"https://api.rawg.io/api/games?search={quote(query)}&page_size=10"
                    data = self._rawg_api_request(search_url)
                    if data: self._send_json_response(data.get('results', []))
                    return

                if len(path_parts) == 4 and path_parts[0:3] == ['api', 'lookup', 'rawg']:
                    game_id = path_parts[3]
                    details_url = f"https://api.rawg.io/api/games/{game_id}?"
                    data = self._rawg_api_request(details_url)
                    if data: self._send_json_response(data)
                    return
                
                # FIXED: Route for getting a single game's details for the details page
                if len(path_parts) == 4 and path_parts[0:3] == ['api', 'editor', 'games']:
                    self.handle_get_editor_game_details(int(path_parts[3]))
                    return
                
                # FIXED: Route for getting the lean list of games for the main editor page
                if path == '/api/editor/games':
                    self.handle_get_editor_games_list()
                    return

                # Fallback to other API routes
                if path == '/api/games': self.handle_get_games_paginated(parsed_path.query)
                elif len(path_parts) == 4 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'collections': self.handle_get_game_collections(int(path_parts[2]), parsed_path.query)
                elif path == '/api/genres': self.handle_get_genres()
                elif path == '/api/collections': self.handle_get_collections(parsed_path.query)
                elif path == '/api/recently_played': self.handle_get_recently_played(parsed_path.query)
                elif path == '/api/newly_added': self.handle_get_newly_added(parsed_path.query)
                elif path == '/api/top_rated': self.handle_get_top_rated(parsed_path.query)
                elif path == '/api/worst_rated': self.handle_get_worst_rated(parsed_path.query)
                elif path == '/api/most_downloaded': self.handle_get_most_downloaded(parsed_path.query)
                elif len(path_parts) == 4 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves': self.handle_list_saves(int(path_parts[2]), parsed_path.query)
                elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves' and path_parts[4] != 'info': self.handle_download_specific_save(int(path_parts[2]), int(path_parts[4]), parsed_path.query)
                elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves' and path_parts[4] == 'info': self.handle_get_save_info(int(path_parts[2]), parsed_path.query)
                elif path == '/api/library/scan': self.handle_library_scan()
                else:
                    self.send_error(404, "API GET endpoint not found.")

            except (ValueError, IndexError):
                self.send_error(400, "Invalid ID format in URL.")
            except Exception as e:
                self.send_error(500, f"Server Error: {e}")
        
        elif path.startswith('/gamelibrary/'):
            handler = http.server.SimpleHTTPRequestHandler
            handler(self.request, self.client_address, self.server, directory=config.PROJECT_ROOT)
        else:
            super().do_GET()

    def do_POST(self):
        path_parts = self.path.strip("/").split("/")
        
        try:
            if len(path_parts) == 4 and path_parts[0:3] == ['api', 'editor', 'games']:
                 self.handle_editor_update(int(path_parts[3]))
                 return

            if self.path == '/api/editor/games':
                self.handle_add_game()
                return

            if len(path_parts) == 4 and path_parts[0:2] == ['api', 'games']:
                game_db_id = int(path_parts[2])
                action = path_parts[3]
                if action == 'status': self.handle_update_status(game_db_id)
                elif action == 'settings': self.handle_update_settings(game_db_id)
                elif action == 'playtime': self.handle_update_playtime(game_db_id)
                elif action == 'favorite': self.handle_update_favorite(game_db_id)
                elif action == 'saves': self.handle_save_upload(game_db_id)
                else: self.send_error(404, "Endpoint action not found.")
                return

            if self.path == '/api/library/scan': self.handle_library_scan()
            elif self.path == '/api/collections': self.handle_create_collection()
            elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'collections'] and path_parts[3] == 'games': self.handle_add_game_to_collection(int(path_parts[2]))
            elif len(path_parts) == 6 and path_parts[0:2] == ['api', 'editor'] and path_parts[2] == 'games' and path_parts[4] == 'upload': self.handle_manual_file_upload(int(path_parts[3]), path_parts[5])
            elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'editor'] and path_parts[2] == 'games':
                game_db_id = int(path_parts[3])
                action = path_parts[4]
                if action == 'poster': self.handle_poster_upload(game_db_id)
                elif action == 'rescan': self.handle_rescan(game_db_id)
                else: self.send_error(404, "Editor action not found.")
            else:
                self.send_error(404, "Invalid API path for POST.")
        except (ValueError, IndexError):
            self.send_error(400, "Invalid ID format in URL.")
        except Exception as e:
            self.send_error(500, f"Server Error: {e}")

    def do_DELETE(self):
        path_parts = self.path.strip("/").split("/")
        try:
            if len(path_parts) == 4 and path_parts[0:3] == ['api', 'editor', 'games']:
                self.handle_delete_game(int(path_parts[3]))
            elif len(path_parts) == 3 and path_parts[0:2] == ['api', 'collections']:
                self.handle_delete_collection(int(path_parts[2]))
            elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'collections'] and path_parts[3] == 'games':
                self.handle_remove_game_from_collection(int(path_parts[2]), int(path_parts[4]))
            elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves':
                self.handle_delete_specific_save(int(path_parts[2]), int(path_parts[4]))
            else:
                self.send_error(404, "Invalid API path for DELETE.")
        except (ValueError, IndexError):
            self.send_error(400, "Invalid ID format in URL.")
        except Exception as e:
            self.send_error(500, f"Server Error: {e}")

    # --- HELPERS ---

    def _get_post_data(self):
        content_length = int(self.headers['Content-Length'])
        post_body = self.rfile.read(content_length)
        return json.loads(post_body)

    def _send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _execute_db_update(self, query, params, get_last_id=False):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            last_id = cursor.lastrowid
            conn.commit()
            if get_last_id: return last_id
            return True
        except Exception as e:
            print(f"DB Update Error: {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()
    # --- HANDLER IMPLEMENTATIONS ---

    def handle_get_genres(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM genres ORDER BY name ASC")
        genres = [{"name": row["name"]} for row in cursor.fetchall()]
        conn.close()
        self._send_json_response(genres)

    def _get_games_from_db(self, query, params, user_id="user_1"):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, params)
        games = []
        rows = cursor.fetchall()
        for row in rows:
            game_dict = dict(row)
            game_db_id = game_dict['id']
            
            # Clean up and format the dictionary
            game_dict['art'] = game_dict.pop('art_path')
            game_dict['executablePath'] = game_dict.pop('executable_path')
            game_dict['launchArgs'] = game_dict.pop('launch_args')
            
            # Fetch related data
            game_dict['genres'] = [g['name'] for g in cursor.execute("SELECT name FROM genres j JOIN game_genres gj ON j.id = gj.genre_id WHERE gj.game_id = ?", (game_db_id,)).fetchall()]
            game_dict['screenshots'] = [s['path'] for s in cursor.execute("SELECT path FROM screenshots WHERE game_id = ?", (game_db_id,)).fetchall()]
            game_dict['install_files'] = [f['filename'] for f in cursor.execute("SELECT filename FROM install_files WHERE game_id = ?", (game_db_id,)).fetchall()]
            game_dict['collections'] = [c['name'] for c in cursor.execute("SELECT c.name FROM collections c JOIN game_collections gc ON c.id = gc.collection_id WHERE gc.game_id = ? AND c.user_id = ?", (game_db_id, user_id)).fetchall()]

            # User-specific data
            game_dict['user_settings'] = {
                'totalPlaytime': game_dict.pop('total_playtime', 0) or 0,
                'executablePath': game_dict.pop('custom_executable_path', None),
                'launchArgs': game_dict.pop('custom_launch_args', None)
            }
            game_dict['is_favorite'] = bool(game_dict.get('is_favorite', 0))
            if game_dict.get('status') is None:
                game_dict['status'] = 'not_installed'

            games.append(game_dict)
        conn.close()
        return games

    def handle_get_recently_played(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        machine_id = params.get('machineId', [None])[0]
        limit = int(params.get('limit', [5])[0])
        
        query = '''
            SELECT g.*, ugd.* FROM games g
            JOIN user_game_data ugd ON g.id = ugd.game_id
            WHERE ugd.user_id = ? AND ugd.machine_id = ? AND ugd.last_played IS NOT NULL
            ORDER BY ugd.last_played DESC
            LIMIT ?
        '''
        games = self._get_games_from_db(query, (user_id, machine_id, limit), user_id)
        self._send_json_response(games)

    def handle_get_newly_added(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        machine_id = params.get('machineId', [None])[0]
        limit = int(params.get('limit', [10])[0])
        
        query = '''
            SELECT g.*, ugd.* FROM games g
            LEFT JOIN user_game_data ugd ON g.id = ugd.game_id AND ugd.user_id = ? AND ugd.machine_id = ?
            ORDER BY g.id DESC
            LIMIT ?
        '''
        games = self._get_games_from_db(query, (user_id, machine_id, limit), user_id)
        self._send_json_response(games)

    def handle_get_top_rated(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        machine_id = params.get('machineId', [None])[0]
        limit = int(params.get('limit', [10])[0])
        
        query = '''
            SELECT g.*, ugd.* FROM games g
            LEFT JOIN user_game_data ugd ON g.id = ugd.game_id AND ugd.user_id = ? AND ugd.machine_id = ?
            WHERE g.rating IS NOT NULL
            ORDER BY g.rating DESC
            LIMIT ?
        '''
        games = self._get_games_from_db(query, (user_id, machine_id, limit), user_id)
        self._send_json_response(games)

    def handle_get_worst_rated(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        machine_id = params.get('machineId', [None])[0]
        limit = int(params.get('limit', [10])[0])
        
        query = '''
            SELECT g.*, ugd.* FROM games g
            LEFT JOIN user_game_data ugd ON g.id = ugd.game_id AND ugd.user_id = ? AND ugd.machine_id = ?
            WHERE g.rating IS NOT NULL AND g.rating > 0
            ORDER BY g.rating ASC
            LIMIT ?
        '''
        games = self._get_games_from_db(query, (user_id, machine_id, limit), user_id)
        self._send_json_response(games)

    def handle_get_most_downloaded(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        machine_id = params.get('machineId', [None])[0]
        limit = int(params.get('limit', [10])[0])
        
        query = '''
            SELECT g.*, ugd.*,
                   (SELECT COUNT(*) FROM user_game_data WHERE game_id = g.id AND status = 'installed' AND user_id = ?) as install_count
            FROM games g
            LEFT JOIN user_game_data ugd ON g.id = ugd.game_id AND ugd.user_id = ? AND ugd.machine_id = ?
            ORDER BY install_count DESC
            LIMIT ?
        '''
        games = self._get_games_from_db(query, (user_id, user_id, machine_id, limit), user_id)
        self._send_json_response(games)

    def handle_get_games_paginated(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        machine_id = params.get('machineId', [None])[0]
        status_filter = params.get('status', ['all'])[0]
        favorites_filter = params.get('favorites', ['false'])[0].lower() == 'true'
        genre_filter = params.get('genre', [None])[0]
        collection_filter = params.get('collection', [None])[0]
        search_term = params.get('search', [''])[0]
        sort_by = params.get('sort', ['title_asc'])[0]
        page = int(params.get('page', [1])[0])
        limit = int(params.get('limit', [50])[0])
        offset = (page - 1) * limit

        conn = get_db_connection()
        cursor = conn.cursor()
        
        base_query = "FROM games g LEFT JOIN user_game_data ugd ON g.id = ugd.game_id AND ugd.user_id = ? AND ugd.machine_id = ?"
        join_clauses = []
        where_clauses = []
        query_params = [user_id, machine_id]
        
        if status_filter == 'installed': where_clauses.append("ugd.status = 'installed'")
        if favorites_filter: where_clauses.append("ugd.is_favorite = 1")
        if search_term:
            where_clauses.append("g.title LIKE ?")
            query_params.append(f'%{search_term}%')
        if genre_filter and genre_filter != 'all':
            join_clauses.append("JOIN game_genres gg ON g.id = gg.game_id JOIN genres j ON gg.genre_id = j.id")
            where_clauses.append("j.name = ?")
            query_params.append(genre_filter)
        if collection_filter:
            join_clauses.append("JOIN game_collections gc ON g.id = gc.game_id JOIN collections c ON gc.collection_id = c.id")
            where_clauses.append("c.name = ? AND c.user_id = ?")
            query_params.extend([collection_filter, user_id])
        
        from_and_joins = base_query + " " + " ".join(join_clauses)
        if where_clauses:
            from_and_joins += " WHERE " + " AND ".join(where_clauses)
            
        count_query = "SELECT COUNT(DISTINCT g.id) " + from_and_joins
        total_games = cursor.execute(count_query, query_params).fetchone()[0]
        total_pages = (total_games + limit - 1) // limit
        conn.close()

        sort_map = {
            'title_asc': 'g.title ASC', 'title_desc': 'g.title DESC',
            'rating_desc': 'g.rating DESC', 'release_date_desc': 'g.release_date DESC'
        }
        order_by_clause = sort_map.get(sort_by, 'g.title ASC')
        
        data_query = "SELECT DISTINCT g.*, ugd.* " + from_and_joins + f" ORDER BY {order_by_clause} LIMIT ? OFFSET ?"
        query_params.extend([limit, offset])
        
        games = self._get_games_from_db(data_query, query_params, user_id)
        response = {
            'games': games,
            'pagination': {'page': page, 'limit': limit, 'totalGames': total_games, 'totalPages': total_pages}
        }
        self._send_json_response(response)

    def handle_get_game_collections(self, game_id, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name FROM collections WHERE user_id = ? ORDER BY name ASC", (user_id,))
        all_user_collections = [{"id": row["id"], "name": row["name"]} for row in cursor.fetchall()]

        cursor.execute("SELECT collection_id FROM game_collections WHERE game_id = ?", (game_id,))
        member_collection_ids = {row["collection_id"] for row in cursor.fetchall()}
        
        conn.close()

        result = []
        for collection in all_user_collections:
            collection['is_member'] = collection['id'] in member_collection_ids
            result.append(collection)

        self._send_json_response(result)

    def handle_get_editor_games(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, developer, rating, description, art_path, executable_path, launch_args, custom_save_path FROM games ORDER BY title ASC")
        games = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self._send_json_response(games)

    def handle_get_collections(self, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM collections WHERE user_id = ? ORDER BY name ASC", (user_id,))
        collections = [{"id": row["id"], "name": row["name"]} for row in cursor.fetchall()]
        conn.close()
        self._send_json_response(collections)

     def handle_add_game(self):
        """Handles POST /api/editor/games - creates a new game."""
        post_data = self._get_post_data()
        title = post_data.get('title')
        if not title:
            return self.send_error(400, "Title is a required field.")

        folder_name = re.sub(r'[^\w\s-]', '', title).strip().lower()
        folder_name = re.sub(r'[-\s]+', '-', folder_name)

        conn = get_db_connection()
        cursor = conn.cursor()
        original_folder_name = folder_name
        counter = 1
        while True:
            cursor.execute("SELECT id FROM games WHERE folder_name = ?", (folder_name,))
            if not cursor.fetchone():
                break
            folder_name = f"{original_folder_name}-{counter}"
            counter += 1

        game_dir = os.path.join(config.GAME_LIBRARY_PATH, folder_name)
        for subdir in ['artwork', 'bonus', 'dlc', 'install', 'patches', 'updates']:
            os.makedirs(os.path.join(game_dir, subdir), exist_ok=True)
        
        query = '''
            INSERT INTO games (title, folder_name, developer, release_date, description, rating, executable_path, launch_args)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            title, folder_name, post_data.get('developer'), post_data.get('release_date'),
            post_data.get('description'), post_data.get('rating'),
            post_data.get('executablePath'), post_data.get('launchArgs')
        )
        
        new_game_id = self._execute_db_update(query, params, get_last_id=True)

        if new_game_id:
            self._send_json_response(
                {'message': 'Game added successfully', 'new_id': new_game_id, 'folder_name': folder_name},
                status_code=201
            )
        else:
            self.send_error(500, "Failed to create game in database.")

    def handle_get_editor_games_list(self):
        """Handles GET /api/editor/games - returns a lean list for the main editor view."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, created_at FROM games ORDER BY title ASC")
        games = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self._send_json_response(games)

    def handle_get_editor_game_details(self, game_id):
        """Handles GET /api/editor/games/<id> - returns full details for one game."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        game = cursor.fetchone()
        conn.close()
        if game:
            self._send_json_response(dict(game))
        else:

    def handle_manual_file_upload(self, game_db_id, category):
        allowed_categories = ['install', 'dlc', 'patches', 'updates', 'bonus', 'artwork']
        if category not in allowed_categories:
            return self.send_error(400, f"Invalid upload category: {category}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_db_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return self.send_error(404, "Game not found for file upload.")
        folder_name = result["folder_name"]

        content_length = int(self.headers.get('content-length', 0))
        if content_length == 0: return self.send_error(400, "Empty request body")

        headers = f"Content-Type: {self.headers['Content-Type']}\n\n".encode('utf-8')
        full_message = headers + self.rfile.read(content_length)
        msg = BytesParser().parsebytes(full_message)

        saved_files = []
        if msg.is_multipart():
            for part in msg.get_payload():
                filename = part.get_filename()
                if filename:
                    filename = os.path.basename(filename)
                    if not filename: continue

                    target_dir = os.path.join(config.GAME_LIBRARY_PATH, folder_name, category)
                    file_path = os.path.join(target_dir, filename)
                    
                    with open(file_path, 'wb') as f: f.write(part.get_payload(decode=True))
                    
                    print(f"Saved uploaded file to: {file_path}")
                    saved_files.append(filename)

                    if category == 'install':
                        cursor.execute("INSERT OR IGNORE INTO install_files (game_id, filename) VALUES (?, ?)", (game_db_id, filename))
                        conn.commit()
        
        conn.close()
        self._send_success_response({'message': f'{len(saved_files)} file(s) uploaded to {category}.', 'files': saved_files})

    def handle_editor_update(self, game_db_id):
        """Handles POST /api/editor/games/<id> - updates an existing game."""
        post_data = self._get_post_data()
        set_clauses, params = [], []
        valid_fields = { 
            "title": "title", "developer": "developer", "release_date": "release_date",
            "rating": "rating", "description": "description", 
            "executable_path": "executable_path", "launch_args": "launch_args", 
            "custom_save_path": "custom_save_path" 
        }
        for key, value in post_data.items():
            if key in valid_fields:
                set_clauses.append(f"{valid_fields[key]} = ?")
                params.append(value)
        if not set_clauses: 
            return self.send_error(400, "No valid fields to update.")
        
        params.append(game_db_id)
        query = f"UPDATE games SET {', '.join(set_clauses)} WHERE id = ?"
        if self._execute_db_update(query, tuple(params)):
            print(f"Editor saved details for game ID: {game_db_id}")
            self._send_json_response({'message': 'Successfully updated game details!'})
        else:
            self.send_error(500, "Failed to update game details.")
        
    def handle_poster_upload(self, game_db_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_db_id,))
        result = cursor.fetchone()
        conn.close()
        if not result:
            return self.send_error(404, "Game not found for poster upload.")
        folder_name = result["folder_name"]
        
        content_length = int(self.headers['Content-Length'])
        image_data = self.rfile.read(content_length)
        
        poster_dir = os.path.join(config.GAME_LIBRARY_PATH, folder_name, 'artwork')
        os.makedirs(poster_dir, exist_ok=True)
        poster_path = os.path.join(poster_dir, 'poster.jpg')

        with open(poster_path, 'wb') as f:
            f.write(image_data)
        print(f"Updated poster for game ID {game_db_id}")
        
        web_path = f"/gamelibrary/{quote(folder_name)}/artwork/poster.jpg"
        self._send_success_response({'new_path': web_path})

    def handle_rescan(self, game_db_id):
        post_data = self._get_post_data()
        new_title = post_data.get('newTitle')
        if not new_title: return self.send_error(400, "Missing 'newTitle' for rescan.")
        
        details = _fetch_game_details(new_title)
        if not details: return self.send_error(404, f"Could not find '{new_title}' on RAWG.")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_db_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return self.send_error(404, "Game to rescan not found in database.")
        folder_name = result["folder_name"]

        # Clean up old data and update with new
        cursor.execute("DELETE FROM game_genres WHERE game_id = ?", (game_db_id,))
        cursor.execute("DELETE FROM screenshots WHERE game_id = ?", (game_db_id,))
        
        # ... (The rest of the rescan logic from your original file)
        
        conn.commit()
        conn.close()
        self._send_success_response({'message': 'Rescan successful!'})

    def handle_update_status(self, game_db_id):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        machine_id = post_data.get('machineId')
        new_status = post_data.get('status')
        if not machine_id: return self.send_error(400, "Missing 'machineId'.")
        if not new_status: return self.send_error(400, "Missing 'status'")
        
        q = 'INSERT INTO user_game_data (user_id, game_id, machine_id, status) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, game_id, machine_id) DO UPDATE SET status = excluded.status'
        if self._execute_db_update(q, (user_id, game_db_id, machine_id, new_status)):
            self._send_success_response()
            print(f"Updated status for game {game_db_id} to '{new_status}'")
        else:
            self.send_error(500, "Database update for status failed.")
    
    def handle_update_settings(self, game_db_id):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        machine_id = post_data.get('machineId')
        settings = post_data.get('settings', {})
        if not machine_id: return self.send_error(400, "Missing 'machineId'.")
        
        q = 'INSERT INTO user_game_data (user_id, game_id, machine_id, custom_executable_path, custom_launch_args) VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, game_id, machine_id) DO UPDATE SET custom_executable_path = excluded.custom_executable_path, custom_launch_args = excluded.custom_launch_args'
        if self._execute_db_update(q, (user_id, game_db_id, machine_id, settings.get('executablePath'), settings.get('launchArgs'))):
            self._send_success_response()
            print(f"Updated settings for game {game_db_id}")
        else:
            self.send_error(500, "Database update for settings failed.")
        
    def handle_update_playtime(self, game_db_id):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        machine_id = post_data.get('machineId')
        duration_ms = post_data.get('durationMs', 0)
        if not machine_id: return self.send_error(400, "Missing 'machineId'.")
        
        q = "INSERT INTO user_game_data (user_id, game_id, machine_id, total_playtime, last_played) VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(user_id, game_id, machine_id) DO UPDATE SET total_playtime = total_playtime + ?, last_played = datetime('now')"
        if self._execute_db_update(q, (user_id, game_db_id, machine_id, duration_ms, duration_ms)):
            self._send_success_response()
            print(f"Updated playtime for game {game_db_id}")
        else:
            self.send_error(500, "Database update for playtime failed.")

    def handle_update_favorite(self, game_db_id):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        machine_id = post_data.get('machineId')
        is_favorite = 1 if post_data.get('favorite', False) else 0
        if not machine_id: return self.send_error(400, "Missing 'machineId'.")
        
        q = 'INSERT INTO user_game_data (user_id, game_id, machine_id, is_favorite) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, game_id, machine_id) DO UPDATE SET is_favorite = excluded.is_favorite'
        if self._execute_db_update(q, (user_id, game_db_id, machine_id, is_favorite)):
            self._send_success_response()
            print(f"Updated favorite status for game {game_db_id} to {is_favorite}")
        else:
            self.send_error(500, "Database update for favorite failed.")

    def handle_create_collection(self):
        post_data = self._get_post_data()
        user_id, name = post_data.get('userId', 'user_1'), post_data.get('name')
        if not name: return self.send_error(400, "Collection name is required.")
        
        new_id = self._execute_db_update("INSERT OR IGNORE INTO collections (user_id, name) VALUES (?, ?)", (user_id, name), get_last_id=True)
        if new_id:
            self._send_success_response({'id': new_id, 'name': name})
            print(f"Created new collection '{name}'")
        else:
            self.send_error(409, "A collection with this name already exists.")

    def handle_delete_game(self, game_db_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_db_id,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return self.send_error(404, "Game not found in database.")
            folder_name = result["folder_name"]
            cursor.execute("DELETE FROM games WHERE id = ?", (game_db_id,))
            conn.commit()
            game_dir_path = os.path.join(config.GAME_LIBRARY_PATH, folder_name)
            if os.path.isdir(game_dir_path):
                shutil.rmtree(game_dir_path)
            self._send_success_response({'message': f'Game and its files have been deleted.'})
        except Exception as e:
            conn.rollback()
            self.send_error(500, f"Server Error during game deletion: {e}")
        finally:
            conn.close()

    def handle_delete_collection(self, collection_id):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM collections WHERE id = ? AND user_id = ?", (collection_id, user_id))
        if not cursor.fetchone():
            conn.close()
            return self.send_error(403, "Collection not found or not owned by user.")
        
        cursor.execute('DELETE FROM collections WHERE id = ? AND user_id = ?', (collection_id, user_id))
        conn.commit()
        conn.close()
        self._send_success_response()
        print(f"Deleted collection ID: {collection_id}")

    def handle_add_game_to_collection(self, collection_id):
        post_data = self._get_post_data()
        game_id = post_data.get('gameId')
        user_id = post_data.get('userId', 'user_1')
        if not game_id: return self.send_error(400, "Missing 'gameId'.")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM collections WHERE id = ? AND user_id = ?", (collection_id, user_id))
        if not cursor.fetchone():
            conn.close()
            return self.send_error(403, "Collection not found or not owned by user.")

        try:
            cursor.execute("INSERT INTO game_collections (collection_id, game_id) VALUES (?, ?)", (collection_id, game_id))
            conn.commit()
            self._send_success_response()
            print(f"Added game {game_id} to collection {collection_id}")
        except sqlite3.IntegrityError:
            self.send_error(409, "Game already in this collection.")
        finally:
            conn.close()
            
    def handle_remove_game_from_collection(self, collection_id, game_id):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        q = "DELETE FROM game_collections WHERE collection_id = ? AND game_id = ? AND EXISTS (SELECT 1 FROM collections WHERE id = ? AND user_id = ?)"
        if self._execute_db_update(q, (collection_id, game_id, collection_id, user_id)):
            self._send_success_response()
            print(f"Removed game {game_id} from collection {collection_id}")
        else:
            self.send_error(500, "Database update failed.")

    def handle_get_save_info(self, game_id, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_id,))
        result = cursor.fetchone()
        conn.close()
        if not result: return self.send_error(404, "Game not found.")
        
        game_folder_name = result["folder_name"]
        save_path = os.path.join(config.SAVES_STORAGE_PATH, user_id, game_folder_name, 'save.zip')

        if os.path.exists(save_path):
            info = {"exists": True, "lastModified": os.path.getmtime(save_path)}
        else:
            info = {"exists": False}
        
        self._send_json_response(info)

    def _get_save_manifest_path(self, user_id, game_folder_name):
        user_save_dir = os.path.join(config.SAVES_STORAGE_PATH, user_id, game_folder_name)
        os.makedirs(user_save_dir, exist_ok=True)
        return os.path.join(user_save_dir, 'saves.json')

    def _read_save_manifest(self, manifest_path):
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                return json.load(f)
        return {"next_version": 1, "limit": config.SAVES_LIMIT, "saves": []}

    def _write_save_manifest(self, manifest_path, manifest_data):
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)

    def handle_list_saves(self, game_id, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_id,))
        result = cursor.fetchone()
        conn.close()
        if not result: return self.send_error(404, "Game not found.")
            
        game_folder_name = result["folder_name"]
        manifest_path = self._get_save_manifest_path(user_id, game_folder_name)
        manifest = self._read_save_manifest(manifest_path)
        
        sorted_saves = sorted(manifest.get('saves', []), key=lambda x: x['timestamp'], reverse=True)
        self._send_json_response(sorted_saves)

    def handle_download_specific_save(self, game_id, save_version, query_string):
        params = parse_qs(query_string)
        user_id = params.get('userId', ['user_1'])[0]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_id,))
        result = cursor.fetchone()
        conn.close()
        if not result: return self.send_error(404, "Game not found.")
        game_folder_name = result["folder_name"]

        manifest_path = self._get_save_manifest_path(user_id, game_folder_name)
        manifest = self._read_save_manifest(manifest_path)
        
        save_to_download = next((s for s in manifest['saves'] if s['version'] == save_version), None)
        if not save_to_download: return self.send_error(404, f"Save version {save_version} not found.")

        save_file_path = os.path.join(config.SAVES_STORAGE_PATH, user_id, game_folder_name, save_to_download['filename'])
        if not os.path.exists(save_file_path): return self.send_error(404, f"Save file for version {save_version} not found on disk.")

        self.send_response(200)
        self.send_header('Content-type', 'application/zip')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        with open(save_file_path, 'rb') as f:
            self.wfile.write(f.read())

    def handle_delete_specific_save(self, game_id, save_version):
        post_data = self._get_post_data()
        user_id = post_data.get('userId', 'user_1')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_id,))
        result = cursor.fetchone()
        conn.close()
        if not result: return self.send_error(404, "Game not found.")
        game_folder_name = result["folder_name"]

        manifest_path = self._get_save_manifest_path(user_id, game_folder_name)
        manifest = self._read_save_manifest(manifest_path)

        save_to_delete = next((s for s in manifest['saves'] if s['version'] == save_version), None)
        if not save_to_delete: return self.send_error(404, f"Save version {save_version} not found.")

        save_file_path = os.path.join(config.SAVES_STORAGE_PATH, user_id, game_folder_name, save_to_delete['filename'])
        if os.path.exists(save_file_path): os.remove(save_file_path)

        manifest['saves'] = [s for s in manifest['saves'] if s['version'] != save_version]
        self._write_save_manifest(manifest_path, manifest)

        self._send_success_response({'message': f'Save version {save_version} deleted successfully.'})

    def handle_save_upload(self, game_id):
        content_type = self.headers.get('Content-Type')
        if not content_type or not content_type.startswith('multipart/form-data'):
            return self.send_error(400, "Content-Type must be multipart/form-data")

        content_length = int(self.headers.get('content-length', 0))
        if content_length == 0: return self.send_error(400, "Empty request body")

        full_message = f"Content-Type: {content_type}\n\n".encode('utf-8') + self.rfile.read(content_length)
        msg = BytesParser().parsebytes(full_message)

        user_id, file_content = None, None
        if msg.is_multipart():
            for part in msg.get_payload():
                disp_params = {k: v.strip('"') for k, v in (p.strip().split('=') for p in part.get('Content-Disposition', '').split(';')[1:] if '=' in p)}
                if disp_params.get('name') == 'userId': user_id = part.get_payload(decode=True).decode('utf-8')
                elif disp_params.get('name') == 'fileData': file_content = part.get_payload(decode=True)

        if not user_id: return self.send_error(400, "Missing 'userId' in form data.")
        if not file_content: return self.send_error(400, "Missing 'fileData' in form data.")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT folder_name FROM games WHERE id = ?", (game_id,))
        result = cursor.fetchone()
        conn.close()
        if not result: return self.send_error(404, "Game not found.")
        game_folder_name = result["folder_name"]

        manifest_path = self._get_save_manifest_path(user_id, game_folder_name)
        manifest = self._read_save_manifest(manifest_path)

        if len(manifest['saves']) >= manifest['limit']:
            manifest['saves'].sort(key=lambda x: x['timestamp'])
            oldest_save = manifest['saves'].pop(0)
            oldest_save_path = os.path.join(config.SAVES_STORAGE_PATH, user_id, game_folder_name, oldest_save['filename'])
            if os.path.exists(oldest_save_path): os.remove(oldest_save_path)

        new_version = manifest['next_version']
        new_filename = f"save_v{new_version}.zip"
        new_save_path = os.path.join(config.SAVES_STORAGE_PATH, user_id, game_folder_name, new_filename)
        
        manifest['saves'].append({"version": new_version, "timestamp": int(time.time() * 1000), "filename": new_filename})
        manifest['next_version'] += 1

        with open(new_save_path, 'wb') as f: f.write(file_content)
        
        self._write_save_manifest(manifest_path, manifest)
        self._send_success_response({'message': 'Save uploaded successfully.'})

    def handle_library_scan(self):
        try:
            print("Library scan requested via API.")
            scanner.scan_library()
            self._send_success_response({'message': 'Scan completed.'})
            print("Library scan finished.")
        except Exception as e:
            self.send_error(500, f"Server Error during scan: {e}")

