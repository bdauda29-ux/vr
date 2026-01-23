from sqlalchemy import text, inspect
from app.database import engine

def run_migrations():
    print("Checking for schema migrations...")
    try:
        # Import models here to avoid circular imports if any
        from app import models
        
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        # --- Multi-Tenancy Migrations ---
        
        # 1. Create organizations table if not exists
        if 'organizations' not in table_names:
            print("Table 'organizations' missing. Creating it...")
            models.Organization.__table__.create(engine)
            print("Table 'organizations' created successfully.")
        else:
            print("Table 'organizations' already exists.")
            # Check for description column
            columns = [c['name'] for c in inspector.get_columns('organizations')]
            if 'description' not in columns:
                print("Column 'description' missing in 'organizations'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE organizations ADD COLUMN description VARCHAR(256)"))
                print("Column 'description' added to 'organizations' successfully.")

        # 2. Add organization_id to existing tables
        # We target: users, staff, offices, audit_logs
        tables_to_update = ['users', 'staff', 'offices', 'audit_logs']
        
        for table in tables_to_update:
            if table in table_names:
                columns = [c['name'] for c in inspector.get_columns(table)]
                if 'organization_id' not in columns:
                    print(f"Column 'organization_id' missing in '{table}'. Adding it...")
                    with engine.connect() as conn:
                        with conn.begin():
                            # Note: SQLite has limited ALTER TABLE support for FKs.
                            # We just add the column. SQLAlchemy models handle the relationship logic.
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN organization_id INTEGER"))
                    print(f"Column 'organization_id' added to '{table}' successfully.")
                else:
                    print(f"Column 'organization_id' already exists in '{table}'.")

        # --- Existing Migrations ---

        if 'staff' in table_names:
            columns = [c['name'] for c in inspector.get_columns('staff')]
            
            if 'login_count' not in columns:
                print("Column 'login_count' missing. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE staff ADD COLUMN login_count INTEGER DEFAULT 0 NOT NULL"))
                print("Column 'login_count' added successfully.")
            
            if 'email' not in columns:
                print("Column 'email' missing. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE staff ADD COLUMN email VARCHAR(128)"))
                print("Column 'email' added successfully.")
            
            if 'allow_edit_rank' not in columns:
                print("Column 'allow_edit_rank' missing. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE staff ADD COLUMN allow_edit_rank INTEGER DEFAULT 0 NOT NULL"))
                print("Column 'allow_edit_rank' added successfully.")

            if 'allow_login' not in columns:
                print("Column 'allow_login' missing. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE staff ADD COLUMN allow_login INTEGER DEFAULT 1 NOT NULL"))
                print("Column 'allow_login' added successfully.")

            if 'allow_edit_dopp' not in columns:
                print("Column 'allow_edit_dopp' missing. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE staff ADD COLUMN allow_edit_dopp INTEGER DEFAULT 0 NOT NULL"))
                print("Column 'allow_edit_dopp' added successfully.")

        # Check for staff_edit_requests table
        if 'staff_edit_requests' not in table_names:
            print("Table 'staff_edit_requests' missing. Creating it...")
            models.StaffEditRequest.__table__.create(engine)
            print("Table 'staff_edit_requests' created successfully.")
        else:
            print("Table 'staff_edit_requests' already exists.")
            
    except Exception as e:
        print(f"Migration Error: {e}")
        import traceback
        traceback.print_exc()
            
if __name__ == "__main__":
    run_migrations()
