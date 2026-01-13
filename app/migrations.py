from sqlalchemy import text, inspect
from app.database import engine

def run_migrations():
    print("Checking for schema migrations...")
    try:
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('staff')]
        
        if 'login_count' not in columns:
            print("Column 'login_count' missing. Adding it...")
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE staff ADD COLUMN login_count INTEGER DEFAULT 0 NOT NULL"))
            print("Column 'login_count' added successfully.")
        else:
            print("Column 'login_count' already exists.")

        if 'email' not in columns:
            print("Column 'email' missing. Adding it...")
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE staff ADD COLUMN email VARCHAR(128)"))
            print("Column 'email' added successfully.")
        else:
            print("Column 'email' already exists.")
            
    except Exception as e:
        print(f"Migration Error: {e}")
            
if __name__ == "__main__":
    run_migrations()
