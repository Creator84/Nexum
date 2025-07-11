import sqlite3
from flask import Flask, jsonify, send_from_directory, abort, request, send_file
import os
import werkzeug.utils

# --- Configuration ---
DATABASE_PATH = os.path.join('database', 'games.db')
GAME_ARCHIVES_DIR = 'GameArchives'
COVER_IMAGES_DIR = 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'zip', '7z', 'rar'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER_ARCHIVES'] = GAME_ARCHIVES_DIR
app.config['UPLOAD_FOLDER_IMAGES'] = COVER_IMAGES_DIR

# --- Helper Functions ---

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def allowed_file(filename):
    """Checks if a file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Management Page Route ---

@app.route('/management')
def management_page():
    """Serves the main management HTML page."""
    return send_file('management.html')

# --- API Routes ---

@app.route('/api/games', methods=['GET'])
def get_games():
    """Endpoint to get a list of all available games."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Could not connect to the database"}), 500
        
    try:
        games_cursor = conn.cursor()
        # Order by name to make it easier to find games in the list
        games_cursor.execute('SELECT Id, Name, Description, PathToCoverImage FROM Games ORDER BY Name ASC')
        games = games_cursor.fetchall()
        conn.close()
        
        game_list = [dict(game) for game in games]
        
        for game in game_list:
            if game.get('PathToCoverImage'):
                game['PathToCoverImage'] = f"/images/{game['PathToCoverImage']}"

        return jsonify(game_list)
    except sqlite3.Error as e:
        return jsonify({"error": f"Database query failed: {e}"}), 500

@app.route('/api/games', methods=['POST'])
def add_game():
    """Endpoint to add a new game to the database."""
    if 'Name' not in request.form:
        return jsonify({"error": "Missing 'Name' field"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Could not connect to the database"}), 500

    image_filename = None
    if 'PathToCoverImage' in request.files:
        file = request.files['PathToCoverImage']
        if file and file.filename != '' and allowed_file(file.filename):
            image_filename = werkzeug.utils.secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], image_filename))

    archive_filename = None
    if 'PathToArchive' in request.files:
        file = request.files['PathToArchive']
        if file and file.filename != '' and allowed_file(file.filename):
            archive_filename = werkzeug.utils.secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER_ARCHIVES'], archive_filename))

    try:
        sql = ''' INSERT INTO Games(Name,Description,ExecutableName,ExecutableArguments,PathToCoverImage,PathToArchive)
                  VALUES(?,?,?,?,?,?) '''
        cursor = conn.cursor()
        cursor.execute(sql, (
            request.form.get('Name'),
            request.form.get('Description'),
            request.form.get('ExecutableName'),
            request.form.get('ExecutableArguments'),
            image_filename,
            archive_filename
        ))
        conn.commit()
        return jsonify({"id": cursor.lastrowid, "message": "Game added successfully"}), 201
    except sqlite3.Error as e:
        return jsonify({"error": f"Database insert failed: {e}"}), 500
    finally:
        conn.close()


@app.route('/api/games/<int:game_id>', methods=['GET'])
def get_game_details(game_id):
    """Endpoint to get detailed information for a single game."""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "Could not connect to the database"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM Games WHERE Id = ?', (game_id,))
        game = cursor.fetchone()
        if game is None: abort(404, description="Game not found")
        
        game_details = dict(game)
        if game_details.get('PathToCoverImage'):
            game_details['PathToCoverImage'] = f"/images/{game_details['PathToCoverImage']}"
        return jsonify(game_details)
    except sqlite3.Error as e:
        return jsonify({"error": f"Database query failed: {e}"}), 500
    finally:
        conn.close()

@app.route('/api/games/<int:game_id>', methods=['PUT'])
def update_game(game_id):
    """Endpoint to update an existing game."""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "Could not connect to the database"}), 500
    
    try:
        # Fetch existing game data to avoid overwriting files with None
        cursor = conn.cursor()
        cursor.execute('SELECT PathToCoverImage, PathToArchive FROM Games WHERE Id = ?', (game_id,))
        existing_game = cursor.fetchone()
        if not existing_game:
            return jsonify({"error": "Game not found"}), 404

        update_data = {
            "Name": request.form.get('Name'),
            "Description": request.form.get('Description'),
            "ExecutableName": request.form.get('ExecutableName'),
            "ExecutableArguments": request.form.get('ExecutableArguments'),
            "PathToCoverImage": existing_game['PathToCoverImage'],
            "PathToArchive": existing_game['PathToArchive']
        }

        if 'PathToCoverImage' in request.files:
            file = request.files['PathToCoverImage']
            if file and file.filename != '' and allowed_file(file.filename):
                image_filename = werkzeug.utils.secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], image_filename))
                update_data['PathToCoverImage'] = image_filename

        if 'PathToArchive' in request.files:
            file = request.files['PathToArchive']
            if file and file.filename != '' and allowed_file(file.filename):
                archive_filename = werkzeug.utils.secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER_ARCHIVES'], archive_filename))
                update_data['PathToArchive'] = archive_filename

        sql = ''' UPDATE Games
                  SET Name = ?, Description = ?, ExecutableName = ?, ExecutableArguments = ?, PathToCoverImage = ?, PathToArchive = ?
                  WHERE Id = ? '''
        cursor.execute(sql, (
            update_data['Name'], update_data['Description'], update_data['ExecutableName'],
            update_data['ExecutableArguments'], update_data['PathToCoverImage'],
            update_data['PathToArchive'], game_id
        ))
        conn.commit()
        return jsonify({"message": "Game updated successfully"}), 200
    except sqlite3.Error as e:
        return jsonify({"error": f"Database update failed: {e}"}), 500
    finally:
        conn.close()

@app.route('/api/games/<int:game_id>', methods=['DELETE'])
def delete_game(game_id):
    """Endpoint to delete a game."""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "Could not connect to the database"}), 500
    try:
        # Optional: Delete files from disk
        cursor = conn.cursor()
        cursor.execute('SELECT PathToCoverImage, PathToArchive FROM Games WHERE Id = ?', (game_id,))
        game_files = cursor.fetchone()
        if game_files:
            if game_files['PathToCoverImage']:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], game_files['PathToCoverImage']))
            if game_files['PathToArchive']:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER_ARCHIVES'], game_files['PathToArchive']))

        cursor.execute('DELETE FROM Games WHERE Id = ?', (game_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Game not found"}), 404
        return jsonify({"message": "Game deleted successfully"}), 200
    except sqlite3.Error as e:
        return jsonify({"error": f"Database delete failed: {e}"}), 500
    except FileNotFoundError:
        # This can happen if file was already deleted, proceed with DB deletion
        return jsonify({"message": "Game deleted from DB, but a file was not found on disk."}), 200
    finally:
        conn.close()


@app.route('/api/games/<int:game_id>/download', methods=['GET'])
def download_game(game_id):
    """Endpoint to download the game archive file."""
    conn = get_db_connection()
    if conn is None: return jsonify({"error": "Could not connect to the database"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT PathToArchive FROM Games WHERE Id = ?', (game_id,))
        game_file_row = cursor.fetchone()
        if game_file_row is None or game_file_row['PathToArchive'] is None:
            abort(404, description="Game archive not found for this ID")
            
        archive_name = game_file_row['PathToArchive']
        
        if not os.path.isfile(os.path.join(GAME_ARCHIVES_DIR, archive_name)):
             abort(404, description="Game archive file does not exist on server")

        return send_from_directory(GAME_ARCHIVES_DIR, archive_name, as_attachment=True)
    except sqlite3.Error as e:
        return jsonify({"error": f"Database query failed: {e}"}), 500
    except FileNotFoundError:
        abort(404, description="File not found on the server.")
    finally:
        conn.close()


@app.route('/images/<filename>')
def serve_image(filename):
    """Serves cover art images."""
    return send_from_directory(COVER_IMAGES_DIR, filename)


# --- Main Execution ---

if __name__ == '__main__':
    # Create necessary directories if they don't exist
    if not os.path.exists(os.path.dirname(DATABASE_PATH)):
        os.makedirs(os.path.dirname(DATABASE_PATH))
    if not os.path.exists(GAME_ARCHIVES_DIR):
        os.makedirs(GAME_ARCHIVES_DIR)
    if not os.path.exists(COVER_IMAGES_DIR):
        os.makedirs(COVER_IMAGES_DIR)
    
    # Add werkzeug to requirements if not present
    app.run(debug=True, host='0.0.0.0', port=5000)
