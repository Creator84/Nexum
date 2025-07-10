# /nexum/database.py

"""
Handles all database operations, including initialization,
schema creation, and migrations.
"""

import sqlite3
import config

def get_db_connection():
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row # Makes it easier to work with results
    return conn

def _migrate_db_add_column(conn, table_name, column_name, column_def):
    """Utility to add a column to a table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row['name'] for row in cursor.fetchall()]
    if column_name in columns:
        print(f"Column '{column_name}' already exists in '{table_name}'. Skipping migration.")
        return

    print(f"Applying database migration: Adding '{column_name}' to '{table_name}' table...")
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        conn.commit()
        print("Database migration successful.")
    except Exception as e:
        print(f"Database migration FAILED: {e}")
        conn.rollback()

def _migrate_db(conn):
    """Checks for and applies necessary database schema migrations."""
    print("Checking for database migrations...")
    try:
        _migrate_db_add_column(conn, "games", "custom_save_path", "TEXT")
        print("Database migration check completed.")
    except Exception as e:
        print(f"Database migration failed: {e}")

def _init_db_tables(cursor):
    """Creates all necessary tables if they don't exist."""
    print("Initializing database tables...")
    cursor.execute("PRAGMA foreign_keys = ON")

    # Main table for static game metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            rawg_id INTEGER UNIQUE,
            title TEXT NOT NULL,
            folder_name TEXT UNIQUE NOT NULL,
            developer TEXT,
            release_date TEXT,
            description TEXT,
            art_path TEXT,
            rating REAL,
            executable_path TEXT,
            launch_args TEXT,
            custom_save_path TEXT
        )
    ''')

    # Tables for many-to-many relationships
    cursor.execute('CREATE TABLE IF NOT EXISTS genres (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS game_genres (game_id INTEGER, genre_id INTEGER, FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE, FOREIGN KEY(genre_id) REFERENCES genres(id) ON DELETE CASCADE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS screenshots (id INTEGER PRIMARY KEY, game_id INTEGER, path TEXT, FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS install_files (id INTEGER PRIMARY KEY, game_id INTEGER, filename TEXT, FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE)')

    # Tables for collections
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(user_id, name)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_collections (
            collection_id INTEGER,
            game_id INTEGER,
            FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE,
            FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
            PRIMARY KEY (collection_id, game_id)
        )
    ''')

    # Table for user-specific data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_game_data (
            user_id TEXT,
            game_id INTEGER,
            machine_id TEXT,
            status TEXT DEFAULT 'not_installed',
            total_playtime INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            last_played DATETIME,
            custom_executable_path TEXT,
            custom_launch_args TEXT,
            PRIMARY KEY (user_id, game_id, machine_id),
            FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
        )
    ''')
    print("Table initialization complete.")

def init_db():
    """Initializes and migrates the database."""
    print("--- Initializing Database ---")
    conn = get_db_connection()
    _migrate_db(conn)
    cursor = conn.cursor()
    _init_db_tables(cursor)
    conn.commit()
    conn.close()
    print("--- Database Initialized ---")
