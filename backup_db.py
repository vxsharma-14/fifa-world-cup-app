import json
from firebase_admin import db
from src.config import initialize_db

def backup_db():
    print("Initializing database connection...")
    # Initialize the app using the project's standard configuration
    initialize_db()
    
    print("Fetching entire database...")
    full_data = db.reference("/").get()
    
    filename = "db_backup_2026_06_12.json"
    with open(filename, "w") as f:
        json.dump(full_data, f, indent=4)
        
    print(f"Backup saved successfully to {filename}")

if __name__ == "__main__":
    backup_db()
