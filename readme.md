Game Launcher Backend ServerThis is a lightweight Flask web server designed to provide a simple backend for a local network game launcher. It serves game metadata from a SQLite database and provides download links for game archives.Project Structure/
|-- app.py                  # The main Flask application
|-- setup_database.py       # Script to initialize the database
|-- requirements.txt        # Python package dependencies
|
|-- database/
|   |-- games.db            # The SQLite database file (created by setup_script.py)
|
|-- GameArchives/
|   |-- StardewValley.zip   # Your game archive files go here
|   |-- Trackmania.zip
|   |-- ...
|
|-- images/
    |-- stardew_valley_cover.jpg # Your game cover art goes here
    |-- trackmania_cover.jpg
    |-- ...
Setup Instructions1. PrerequisitesPython 3.6+ installed on your system.pip for installing packages.2. InstallationClone or Download: Download the files and place them in a new project folder.Install Dependencies: Open a terminal or command prompt in the project folder and run:pip install -r requirements.txt
3. Initialize the DatabaseBefore running the server for the first time, you must set up the database. This command will create the database/games.db file, create the necessary Games table, and populate it with some sample game data. It will also create dummy archive and image files for testing.Run the following command in your terminal:python setup_database.py
4. Add Your GamesGame Archives: Place your game archives (e.g., .zip, .7z) into the GameArchives/ folder.Cover Art: Place your cover images into the images/ folder.Update Database: You can manually add or edit entries in the games.db file using a SQLite browser tool (like DB Browser for SQLite) to match the files you've added. Make sure the PathToArchive and PathToCoverImage columns match the filenames exactly.Running the ServerOnce the setup is complete, you can start the server with the following command:python app.py
The server will start and be accessible on your local network. By default, it runs on http://0.0.0.0:5000. This means it will be available at http://<your-server-ip>:5000 to other computers on your network.API EndpointsGET /api/gamesDescription: Returns a JSON list of all games.Example Response:[
  {
    "Description": "A farming simulation role-playing game.",
    "Id": 1,
    "Name": "Stardew Valley",
    "PathToCoverImage": "/images/stardew_valley_cover.jpg"
  },
  ...
]
GET /api/games/<id>Description: Returns detailed information for a single game specified by its id.Example Response (/api/games/1):{
  "Description": "A farming simulation role-playing game.",
  "ExecutableArguments": "",
  "ExecutableName": "Stardew Valley.exe",
  "Id": 1,
  "Name": "Stardew Valley",
  "PathToArchive": "StardewValley.zip",
  "PathToCoverImage": "/images/stardew_valley_cover.jpg"
}
GET /api/games/<id>/downloadDescription: Initiates a download of the game archive file for the specified game id. The response will be the raw file stream, not JSON.