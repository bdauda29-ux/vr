from sqlalchemy import text
from app.database import engine

def run_migrations():
    print("Checking for schema migrations...")
    with engine.connect() as conn:
        try:
            # Check if login_count column exists in staff table
            # This query works for both SQLite and PostgreSQL
            try:
                # Try to select the column. If it fails, it doesn't exist.
                conn.execute(text("SELECT login_count FROM staff LIMIT 1"))
                print("Column 'login_count' already exists.")
            except Exception:
                print("Column 'login_count' missing. Adding it...")
                # Add the column
                # Note: 'ALTER TABLE' syntax is generally compatible, but we need to handle transaction
                conn.execute(text("ALTER TABLE staff ADD COLUMN login_count INTEGER DEFAULT 0 NOT NULL"))
                conn.commit()
                print("Column 'login_count' added successfully.")
                
        except Exception as e:
            print(f"Migration Error: {e}")
            # Don't raise, let the app try to start anyway
            
if __name__ == "__main__":
    run_migrations()
