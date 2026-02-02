import sqlite3
import os

DB_FILE = "vss.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 1. Create custom_field_definitions table
    print("Creating custom_field_definitions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_field_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(64) NOT NULL UNIQUE,
            label VARCHAR(128) NOT NULL,
            field_type VARCHAR(32) NOT NULL DEFAULT 'text',
            is_active BOOLEAN DEFAULT 1
        )
    """)
    
    # 2. Add custom_data column to staff table
    print("Checking if custom_data column exists in staff table...")
    try:
        cursor.execute("SELECT custom_data FROM staff LIMIT 1")
        print("custom_data column already exists.")
    except sqlite3.OperationalError:
        print("Adding custom_data column to staff table...")
        try:
            cursor.execute("ALTER TABLE staff ADD COLUMN custom_data TEXT")
            print("custom_data column added successfully.")
        except Exception as e:
            print(f"Error adding column: {e}")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
