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
            if 'description' in columns:
                print("Column 'description' found in 'formations'. Dropping it...")
                try:
                    with engine.connect() as conn:
                        with conn.begin():
                            conn.execute(text("ALTER TABLE formations DROP COLUMN description"))
                    print("Column 'description' dropped from 'formations' successfully.")
                except Exception as e:
                    print(f"Failed to drop column 'description' (might be SQLite limitation): {e}")

            # Check for formation_type and parent_id
            columns = [c['name'] for c in inspector.get_columns('formations')]
            if 'formation_type' not in columns:
                print("Column 'formation_type' missing in 'formations'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE formations ADD COLUMN formation_type VARCHAR(32)"))
                print("Column 'formation_type' added to 'formations' successfully.")
            
            if 'parent_id' not in columns:
                print("Column 'parent_id' missing in 'formations'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE formations ADD COLUMN parent_id INTEGER"))
                print("Column 'parent_id' added to 'formations' successfully.")

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

        # 4. Add office_id to audit_logs
        if 'audit_logs' in table_names:
            columns = [c['name'] for c in inspector.get_columns('audit_logs')]
            if 'office_id' not in columns:
                print("Column 'office_id' missing in 'audit_logs'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN office_id INTEGER"))
                print("Column 'office_id' added to 'audit_logs' successfully.")

            if 'user_id' not in columns:
                print("Column 'user_id' missing in 'audit_logs'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN user_id INTEGER"))
                print("Column 'user_id' added to 'audit_logs' successfully.")
                
            if 'username' not in columns:
                print("Column 'username' missing in 'audit_logs'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN username VARCHAR(64)"))
                print("Column 'username' added to 'audit_logs' successfully.")

        # 5. Create notifications table if missing, or update it
        if 'notifications' not in table_names:
            print("Table 'notifications' missing. Creating it...")
            models.Notification.__table__.create(engine)
            print("Table 'notifications' created successfully.")
        else:
            print("Table 'notifications' exists. Checking columns...")
            columns = [c['name'] for c in inspector.get_columns('notifications')]
            
            if 'user_id' not in columns:
                print("Column 'user_id' missing in 'notifications'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE notifications ADD COLUMN user_id INTEGER"))
            
            if 'staff_id' not in columns:
                print("Column 'staff_id' missing in 'notifications'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(text("ALTER TABLE notifications ADD COLUMN staff_id INTEGER"))
                        
            if 'timestamp' not in columns:
                 # Check if created_at exists, maybe alias or just add timestamp
                 if 'created_at' in columns:
                     # We can just use created_at, but model has timestamp. Let's add timestamp for consistency or alias it.
                     # But since we defined timestamp in model, let's add it.
                     pass # Assuming created_at covers it, but model has both? 
                     # Wait, model says: timestamp = Column(..., server_default=func.now())
                     # And created_at = Column(...)
                     # If created_at exists, we might not need timestamp if we map them.
                     # But better to match model.
                     print("Column 'timestamp' missing in 'notifications'. Adding it...")
                     with engine.connect() as conn:
                        with conn.begin():
                            # Default to now
                            conn.execute(text("ALTER TABLE notifications ADD COLUMN timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"))

        # 6. Custom Data column for Staff
        if 'staff' in table_names:
            columns = [c['name'] for c in inspector.get_columns('staff')]
            if 'custom_data' not in columns:
                print("Column 'custom_data' missing in 'staff'. Adding it...")
                with engine.connect() as conn:
                    with conn.begin():
                        # Text or JSON/JSONB depending on DB. using Text/String for compatibility
                        conn.execute(text("ALTER TABLE staff ADD COLUMN custom_data TEXT"))
                print("Column 'custom_data' added to 'staff' successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migrations()
