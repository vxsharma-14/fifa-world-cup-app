import re
from firebase_admin import db, credentials, initialize_app

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey.json')
initialize_app(cred, {'databaseURL': 'https://fifa-world-cup-app-default-rtdb.firebaseio.com/'})

def convert_ist_to_et_string(ist_str: str) -> str:
    """Simple replacement based on observed format."""
    return ist_str.replace("IST", "ET")

def migrate():
    print("Starting migration...")
    
    # 1. Migrate daily_predictions submitted_at
    ref = db.reference("daily_predictions")
    predictions = ref.get()
    for user, dates in predictions.items():
        for date, data in dates.items():
            if "submitted_at" in data:
                new_ts = convert_ist_to_et_string(data["submitted_at"])
                ref.child(f"{user}/{date}/submitted_at").set(new_ts)
    print("Migrated daily_predictions")

    # 2. Migrate points_audit updated_at
    ref = db.reference("points_audit")
    audit = ref.get()
    for user, data in audit.items():
        for match_id, m_data in data.get("match_results", {}).items():
            if "updated_at" in m_data:
                new_ts = convert_ist_to_et_string(m_data["updated_at"])
                ref.child(f"{user}/match_results/{match_id}/updated_at").set(new_ts)
    print("Migrated points_audit")

    # 3. Migrate pre_tournament submitted_at
    ref = db.reference("pre_tournament")
    pre_t = ref.get()
    for user, data in pre_t.items():
        if "submitted_at" in data:
            new_ts = convert_ist_to_et_string(data["submitted_at"])
            ref.child(f"{user}/submitted_at").set(new_ts)
    print("Migrated pre_tournament")
    
    # 4. Migrate results updated_at
    ref = db.reference("results")
    results = ref.get()
    if results:
        for match_id, data in results.items():
            if "updated_at" in data:
                new_ts = convert_ist_to_et_string(data["updated_at"])
                ref.child(f"{match_id}/updated_at").set(new_ts)
        print("Migrated results")

    print("Migration complete!")

if __name__ == "__main__":
    migrate()
