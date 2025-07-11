import sqlite3
import os

# --- Configuration ---
DATABASE_PATH = os.path.join('database', 'games.db')
GAME_ARCHIVES_DIR = 'GameArchives'
COVER_IMAGES_DIR = 'images'

def setup_database():
    """
    Sets up the SQLite database.
    Creates the Games table and inserts some sample data.
    """
    # Ensure the database directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    # Connect to the database (it will be created if it doesn't exist)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # --- Create the Games Table ---
    # Using IF NOT EXISTS to prevent errors on re-running the script
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Games (
        Id INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Description TEXT,
        PathToArchive TEXT NOT NULL,
        PathToCoverImage TEXT,
        ExecutableName TEXT,
        ExecutableArguments TEXT
    );
    ''')

    print("'Games' table created or already exists.")

    # --- Insert Sample Data ---
    # For idempotency, we can check if data already exists
    cursor.execute("SELECT COUNT(Id) FROM Games")
    if cursor.fetchone()[0] == 0:
        sample_games = [
            (
                'Stardew Valley',
                'A farming simulation role-playing game.',
                'StardewValley.zip',
                'stardew_valley_cover.jpg',
                'Stardew Valley.exe',
                ''
            ),
            (
                'Trackmania Nations Forever',
                'A fast-paced, free-to-play online racing game.',
                'Trackmania.zip',
                'trackmania_cover.jpg',
                'TmForever.exe',
                '/nolaunch /nodialog'
            ),
            (
                'Warcraft III: The Frozen Throne',
                'A high fantasy real-time strategy computer game.',
                'Warcraft3.zip',
                'warcraft3_cover.jpg',
                'Frozen Throne.exe',
                '-opengl'
            )
        ]

        cursor.executemany('''
        INSERT INTO Games (Name, Description, PathToArchive, PathToCoverImage, ExecutableName, ExecutableArguments)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_games)
        
        print(f"{len(sample_games)} sample games inserted.")
    else:
        print("Database already contains data. Skipping sample data insertion.")

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    
    print("Database setup complete.")

def create_dummy_files():
    """
    Creates placeholder files for game archives and images
    to ensure the download links and image links work for testing.
    """
    print("Creating dummy files for testing...")
    
    # Create directories
    os.makedirs(GAME_ARCHIVES_DIR, exist_ok=True)
    os.makedirs(COVER_IMAGES_DIR, exist_ok=True)
    
    # Dummy game archives
    dummy_archives = ['StardewValley.zip', 'Trackmania.zip', 'Warcraft3.zip']
    for archive in dummy_archives:
        filepath = os.path.join(GAME_ARCHIVES_DIR, archive)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(f"This is a dummy archive for {archive}.\n")
            print(f"Created dummy file: {filepath}")

    # Dummy cover images
    dummy_images = ['stardew_valley_cover.jpg', 'trackmania_cover.jpg', 'warcraft3_cover.jpg']
    for image in dummy_images:
        filepath = os.path.join(COVER_IMAGES_DIR, image)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(f"This is a dummy image for {image}.\n")
            print(f"Created dummy file: {filepath}")
            
    print("Dummy file creation complete.")


if __name__ == '__main__':
    setup_database()
    create_dummy_files()
