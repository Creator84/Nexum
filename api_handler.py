# /nexum/api_handler.py

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
import time
from email.parser import BytesParser
from urllib.parse import urlparse, parse_qs, quote

import config
import scanner
from database import get_db_connection

class GameAPIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve files from the 'static' directory
        super().__init__(*args, directory=config.STATIC_FILES_PATH, **kwargs)

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

        # API routes
        if path.startswith('/api/'):
            if path == '/api/games':
                self.handle_get_games_paginated(parsed_path.query)
            elif len(path_parts) == 4 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'collections':
                self.handle_get_game_collections(int(path_parts[2]), parsed_path.query)
            elif path == '/api/genres':
                self.handle_get_genres()
            elif path == '/api/collections':
                self.handle_get_collections(parsed_path.query)
            elif path == '/api/recently_played':
                self.handle_get_recently_played(parsed_path.query)
            elif path == '/api/newly_added':
                self.handle_get_newly_added(parsed_path.query)
            elif path == '/api/top_rated':
                self.handle_get_top_rated(parsed_path.query)
            elif path == '/api/worst_rated':
                self.handle_get_worst_rated(parsed_path.query)
            elif path == '/api/most_downloaded':
                self.handle_get_most_downloaded(parsed_path.query)
            elif path == '/api/editor/games':
                self.handle_get_editor_games()
            elif len(path_parts) == 4 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves':
                self.handle_list_saves(int(path_parts[2]), parsed_path.query)
            elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves':
                self.handle_download_specific_save(int(path_parts[2]), int(path_parts[4]), parsed_path.query)
            elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves' and path_parts[4] == 'info':
                self.handle_get_save_info(int(path_parts[2]), parsed_path.query)
            elif path == '/api/library/scan':
                self.handle_library_scan()
            else:
                self.send_error(404, "API GET endpoint not found.")
        # Static file serving
        else:
            # The superclass's __init__ already points to the static dir.
            # We need to adjust the path to look inside the gamelibrary for assets.
            if self.path.startswith('/static/gamelibrary/'):
                self.path = self.path[len('/static'):] # Strip /static prefix
                # Now self.path is e.g. /gamelibrary/game-folder/artwork/poster.jpg
                # The default handler will look for ./gamelibrary/...
                # We need to change the directory temporarily for this request
                # This is tricky with SimpleHTTPRequestHandler. Let's adjust the path instead.
                # A better solution would be a more robust web framework (like Flask or FastAPI).
                # For now, we'll rely on the file structure and URL paths matching.
                # The scanner now saves paths like /gamelibrary/...
                # We need to serve the gamelibrary folder as well.
                # The easiest way is to create a symlink `static/gamelibrary` -> `../gamelibrary`
                # Or, handle it manually here.
                
                # Manual handling for game library assets
                # This makes the server serve files from the project root for these specific paths.
                super(GameAPIHandler, self).__init__(*self.args, directory=config.PROJECT_ROOT, **self.kwargs)
                return

            super().do_GET()


    def do_POST(self):
        path_parts = self.path.strip("/").split("/")
        
        if self.path == '/api/editor/games':
            self.handle_add_game()
        elif len(path_parts) == 4 and path_parts[0:2] == ['api', 'games']:
            game_db_id = int(path_parts[2])
            action = path_parts[3]
            if action == 'status': self.handle_update_status(game_db_id)
            elif action == 'settings': self.handle_update_settings(game_db_id)
            elif action == 'playtime': self.handle_update_playtime(game_db_id)
            elif action == 'favorite': self.handle_update_favorite(game_db_id)
            elif action == 'saves': self.handle_save_upload(game_db_id)
            else: self.send_error(404, "Endpoint action not found.")
        elif self.path == '/api/library/scan':
            self.handle_library_scan()
        elif self.path == '/api/collections':
            self.handle_create_collection()
        elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'collections'] and path_parts[3] == 'games':
            self.handle_add_game_to_collection(int(path_parts[2]))
        elif len(path_parts) == 6 and path_parts[0:2] == ['api', 'editor'] and path_parts[2] == 'games' and path_parts[4] == 'upload':
            self.handle_manual_file_upload(int(path_parts[3]), path_parts[5])
        elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'editor'] and path_parts[2] == 'games':
            game_db_id = int(path_parts[3])
            action = path_parts[4]
            if action == 'poster': self.handle_poster_upload(game_db_id)
            elif action == 'rescan': self.handle_rescan(game_db_id)
            else: self.send_error(404, "Editor action not found.")
        elif len(path_parts) == 4 and path_parts[0:2] == ['api', 'editor'] and path_parts[2] == 'games':
            self.handle_editor_update(int(path_parts[3]))
        else:
            self.send_error(404, "Invalid API path for POST.")

    def do_DELETE(self):
        path_parts = self.path.strip("/").split("/")
        
        if len(path_parts) == 4 and path_parts[0:2] == ['api', 'editor'] and path_parts[2] == 'games':
            self.handle_delete_game(int(path_parts[3]))
        elif len(path_parts) == 3 and path_parts[0:2] == ['api', 'collections']:
            self.handle_delete_collection(int(path_parts[2]))
        elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'collections'] and path_parts[3] == 'games':
            self.handle_remove_game_from_collection(int(path_parts[2]), int(path_parts[4]))
        elif len(path_parts) == 5 and path_parts[0:2] == ['api', 'games'] and path_parts[3] == 'saves':
            self.handle_delete_specific_save(int(path_parts[2]), int(path_parts[4]))
        else:
            self.send_error(404, "Invalid API path for DELETE.")

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

    def _send_success_response(self, data=None):
        response_data = {'success': True}
        if data:
            response_data.update(data)
        self._send_json_response(response_data)

    def _execute_db_update(self, query, params, get_last_id=False):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            last_id = cursor.lastrowid
            conn.commit()
            conn.close()
            if get_last_id:
                return last_id
            return True
        except Exception as e:
            print(f"DB Update Error: {e}")
            return False

    # --- HANDLER IMPLEMENTATIONS ---
    # Note: These are mostly copied from your original file.
    # In a larger refactor, these could be moved to their own modules.

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

    # ... other handle_* methods from your original file would go here ...
    # This is to keep the example concise. You would copy all your handler
    # methods (like handle_get_recently_played, handle_update_status, etc.) here.
    # Make sure to replace sqlite3.connect(DATABASE_PATH) with get_db_connection()
    # and adjust paths to use the config module.

    def handle_library_scan(self):
        """Handles a request to scan the library for new games."""
        try:
            print("Library scan for new games requested via API.")
            # This is a blocking call. For a real app, consider a background thread.
            scanner.scan_library()
            self._send_success_response({'message': 'Scan for new games completed.'})
            print("Library scan finished.")
        except Exception as e:
            self.send_error(500, f"Server Error during scan: {e}")

    def handle_editor_update(self, game_db_id):
        post_data = self._get_post_data()
        set_clauses, params = [], []
        valid_fields = { 
            "title": "title", "developer": "developer", "description": "description", 
            "rating": "rating", "executablePath": "executable_path", 
            "launchArgs": "launch_args", "custom_save_path": "custom_save_path" 
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
            self._send_success_response({'message': 'Successfully updated game details!'})
        else:
            self.send_error(500, "Failed to update game details.")

    def handle_delete_game(self, game_db_id):
        """Deletes a game from the database and its folder from the filesystem."""
        print(f"Attempting to delete game with ID: {game_db_id}")
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
            print(f"  > Deleted game ID {game_db_id} from database.")

            game_dir_path = os.path.join(config.GAME_LIBRARY_PATH, folder_name)
            if os.path.isdir(game_dir_path):
                shutil.rmtree(game_dir_path)
                print(f"  > Deleted directory: {game_dir_path}")
            
            self._send_success_response({'message': f'Game and its files have been deleted.'})
        except Exception as e:
            conn.rollback()
            self.send_error(500, f"Server Error during game deletion: {e}")
        finally:
            conn.close()
