# /nexum/main.py

"""
Main entry point for the GamePlex application.
Use this script to either scan the library or run the API server.
"""

import sys
import server
import scanner

def main():
    """Parses command-line arguments to decide which action to perform."""
    if len(sys.argv) < 2 or sys.argv[1] not in ['scan', 'serve']:
        print("Usage: python main.py [scan|serve]")
        print("  scan  - Scans the game library for new games and updates the database.")
        print("  serve - Starts the GamePlex API server.")
        sys.exit(1)

    action = sys.argv[1]

    if action == 'scan':
        print("Starting library scan...")
        scanner.scan_library()
        print("Scan complete.")
    elif action == 'serve':
        print("Starting server...")
        server.run()

if __name__ == "__main__":
    main()
