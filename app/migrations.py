from sqlalchemy import text, inspect
from app.database import engine

def run_migrations():
    print("Checking for schema migrations...")
    try:
        # Import models here to avoid circular imports if any
        from app import models
        
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        
        # --- Formation Refactor Migrations ---
        
        # 1. Rename organizations table to formations
        if 'organizations' in table_names and 'formations' not in table_names:
            print("Renaming table 'organizations' to 'formations'...")
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(text("ALTER TABLE organizations RENAME TO formations"))
            print("Table renamed successfully.")
            # Refresh table names
            table_names = inspector.get_table_names()

        # 2. Create formations table if not exists (and wasn't renamed)
        if 'formations' not in table_names:
            print("Table 'formations' missing. Creating it...")
            models.Formation.__table__.create(engine)
            print("Table 'formations' created successfully.")
        else:
            print("Table 'formations' already exists.")
            # Check for description column
            columns = [c['name'] for c in inspector.get_columns('formations')]
            if 'description' not in columns:
                print("Column 'description' missing in 'formations'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE formations ADD COLUMN description VARCHAR(256)"))
                print("Column 'description' added to 'formations' successfully.")

        # 3. Rename/Add formation_id to existing tables
        tables_to_update = ['users', 'staff', 'offices', 'audit_logs']
        
        for table in tables_to_update:
            if table in table_names:
                columns = [c['name'] for c in inspector.get_columns(table)]
                
                # Check for old column name
                if 'organization_id' in columns and 'formation_id' not in columns:
                    print(f"Renaming 'organization_id' to 'formation_id' in '{table}'...")
                    with engine.connect() as conn:
                        with conn.begin():
                            conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN organization_id TO formation_id"))
                    print(f"Renamed 'organization_id' to 'formation_id' in '{table}'.")
                
                # Check for new column name (if rename didn't happen or wasn't needed)
                columns = [c['name'] for c in inspector.get_columns(table)] # Refresh columns
                if 'formation_id' not in columns:
                    print(f"Column 'formation_id' missing in '{table}'. Adding it...")
                    with engine.connect() as conn:
                        with conn.begin():
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN formation_id INTEGER"))
                    print(f"Column 'formation_id' added to '{table}' successfully.")
                else:
                    print(f"Column 'formation_id' already exists in '{table}'.")

        # --- Existing Migrations ---

        if 'offices' in table_names:
            columns = [c['name'] for c in inspector.get_columns('offices')]
            
            if 'office_type' not in columns:
                print("Column 'office_type' missing in 'offices'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE offices ADD COLUMN office_type VARCHAR(32)"))
                print("Column 'office_type' added successfully.")
            
            if 'parent_id' not in columns:
                print("Column 'parent_id' missing in 'offices'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE offices ADD COLUMN parent_id INTEGER"))
                print("Column 'parent_id' added successfully.")

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
