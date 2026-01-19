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
        
        if 'allow_edit_rank' not in columns:
            print("Column 'allow_edit_rank' missing. Adding it...")
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE staff ADD COLUMN allow_edit_rank INTEGER DEFAULT 0 NOT NULL"))
            print("Column 'allow_edit_rank' added successfully.")
        else:
            print("Column 'allow_edit_rank' already exists.")

        if 'allow_login' not in columns:
            print("Column 'allow_login' missing. Adding it...")
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE staff ADD COLUMN allow_login INTEGER DEFAULT 1 NOT NULL"))
            print("Column 'allow_login' added successfully.")
        else:
            print("Column 'allow_login' already exists.")

        if 'allow_edit_dopp' not in columns:
            print("Column 'allow_edit_dopp' missing. Adding it...")
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE staff ADD COLUMN allow_edit_dopp INTEGER DEFAULT 0 NOT NULL"))
            print("Column 'allow_edit_dopp' added successfully.")
        else:
            print("Column 'allow_edit_dopp' already exists.")

        # Check for staff_edit_requests table
        if 'staff_edit_requests' not in inspector.get_table_names():
            print("Table 'staff_edit_requests' missing. Creating it...")
            from app.models import StaffEditRequest
            StaffEditRequest.__table__.create(engine)
            print("Table 'staff_edit_requests' created successfully.")
        else:
            print("Table 'staff_edit_requests' already exists.")
            
    except Exception as e:
        print(f"Migration Error: {e}")
            
if __name__ == "__main__":
    run_migrations()
