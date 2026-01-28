import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text
from app.database import DB_URL

def run_migrations():
    print(f"Connecting to {DB_URL}...")
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        # 1. Add user_id and username to audit_logs
        # SQLite doesn't support IF NOT EXISTS for ADD COLUMN, so we use try-except
        try:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN user_id INTEGER"))
            print("Added user_id to audit_logs")
        except Exception as e:
            print(f"info: user_id column might already exist or error: {e}")

        try:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN username VARCHAR(64)"))
            print("Added username to audit_logs")
        except Exception as e:
            print(f"info: username column might already exist or error: {e}")

        # 2. Hierarchy Update
        # Find SHQ ID
        print("Updating Hierarchy...")
        result = conn.execute(text("SELECT id FROM formations WHERE code = 'SHQ' OR name LIKE '%Service Headquarters%' LIMIT 1"))
        shq = result.fetchone()
        
        if shq:
            shq_id = shq[0]
            print(f"Found SHQ ID: {shq_id}")
            
            # Update Directorates
            # The user said "including V/R". If V/R is a Formation, ensure its parent is SHQ.
            # We target all Directorates.
            result_update = conn.execute(text(f"UPDATE formations SET parent_id = {shq_id} WHERE formation_type = 'Directorate'"))
            print(f"Updated {result_update.rowcount} Directorates to be under SHQ")
            
            # Specifically check for V/R if it's not a Directorate type but named V/R
            result_vr = conn.execute(text(f"UPDATE formations SET parent_id = {shq_id} WHERE (code = 'V/R' OR name LIKE '%Visa/Residency%') AND parent_id IS NULL"))
            if result_vr.rowcount > 0:
                print(f"Updated {result_vr.rowcount} V/R entries explicitly.")
                
        else:
            print("SHQ not found! Cannot re-parent Directorates.")
            
        conn.commit()
        print("Migration completed.")

if __name__ == "__main__":
    run_migrations()
