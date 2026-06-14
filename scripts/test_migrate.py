import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firebase_admin import db
from src.config import initialize_db

# Use project's established connection logic
initialize_db()

def convert_ist_to_et_string(ist_str: str) -> str:
    return ist_str.replace("IST", "ET")

def test_migration():
    print("--- Test Migration Mode ---")
    
    # 1. Target a single node
    path = "pre_tournament"
    ref = db.reference(path)
    data = ref.get()
    
    if not data:
        print("No data found at path.")
        return

    # Get first user's record
    user = list(data.keys())[0]
    record = data[user]
    
    if "submitted_at" not in record:
        print(f"No 'submitted_at' found for user {user}")
        return
        
    old_val = record["submitted_at"]
    new_val = convert_ist_to_et_string(old_val)
    
    print(f"Testing on node: {path}/{user}/submitted_at")
    print(f"Old Value: {old_val}")
    print(f"New Value: {new_val}")
    
    confirm = input("Proceed with saving THIS node? (y/n): ")
    if confirm.lower() == 'y':
        ref.child(f"{user}/submitted_at").set(new_val)
        print("Update saved successfully.")
    else:
        print("Update cancelled.")

if __name__ == "__main__":
    test_migration()
