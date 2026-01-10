from app.database import engine
from sqlalchemy import text

def fix_schema():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE staff ADD COLUMN out_request_status VARCHAR(32)"))
            print("Added out_request_status")
        except Exception as e:
            print(f"out_request_status error: {e}")
            
        try:
            conn.execute(text("ALTER TABLE staff ADD COLUMN out_request_date DATE"))
            print("Added out_request_date")
        except Exception as e:
            print(f"out_request_date error: {e}")
            
        try:
            conn.execute(text("ALTER TABLE staff ADD COLUMN out_request_reason VARCHAR(64)"))
            print("Added out_request_reason")
        except Exception as e:
            print(f"out_request_reason error: {e}")

if __name__ == "__main__":
    fix_schema()
