import sys
import os

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, get_db, engine
from app import crud
from app import models
import datetime
from sqlalchemy.orm import sessionmaker

def test_filters():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Create Test Formation
        fmt = crud.create_formation(db, "Test Formation Filter", "TFF", formation_type="State Command")
        print(f"Created Formation: {fmt.id}")
        
        # 2. Create Test Office
        off = crud.create_office(db, "Test Office Filter", fmt.id, "Section")
        print(f"Created Office: {off.id} - {off.name}")
        
        # 3. Create Test Staff
        staff_data = {
            "nis_no": "FILTER123",
            "surname": "Filter",
            "other_names": "Test",
            "rank": "ASI 1",
            "formation_id": fmt.id,
            "office": "Test Office Filter",
            "dofa": datetime.date(2020, 1, 1),
            "dob": datetime.date(1990, 1, 1),
            "state_id": 1,
            "lga_id": 1,
            "gender": "Male",
            "phone_no": "08000000000"
        }
        staff = crud.create_staff(db, staff_data)
        print(f"Created Staff: {staff.id} - Rank: {staff.rank} - Office: {staff.office}")
        
        # 4. Test Rank Filter (Match)
        print("\n--- Testing Rank Filter (Match) ---")
        items, count = crud.list_staff(db, rank=["ASI 1"], include_count=True)
        found = any(s.id == staff.id for s in items)
        print(f"Filter rank=['ASI 1']: Found={found}, Total={count}")
        
        # 5. Test Rank Filter (No Match)
        print("\n--- Testing Rank Filter (No Match) ---")
        items, count = crud.list_staff(db, rank=["CGI"], include_count=True)
        found = any(s.id == staff.id for s in items)
        print(f"Filter rank=['CGI']: Found={found}, Total={count}")

        # 6. Test Office Filter (Match)
        print("\n--- Testing Office Filter (Match) ---")
        items, count = crud.list_staff(db, office=["Test Office Filter"], include_count=True)
        found = any(s.id == staff.id for s in items)
        print(f"Filter office=['Test Office Filter']: Found={found}, Total={count}")

        # 7. Test Office Filter (No Match)
        print("\n--- Testing Office Filter (No Match) ---")
        items, count = crud.list_staff(db, office=["Non Existent"], include_count=True)
        found = any(s.id == staff.id for s in items)
        print(f"Filter office=['Non Existent']: Found={found}, Total={count}")

        # 8. Test Combined Filter
        print("\n--- Testing Combined Filter ---")
        items, count = crud.list_staff(db, rank=["ASI 1"], office=["Test Office Filter"], include_count=True)
        found = any(s.id == staff.id for s in items)
        print(f"Filter rank=['ASI 1'], office=['Test Office Filter']: Found={found}, Total={count}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            if 'staff' in locals(): db.delete(staff)
            if 'off' in locals(): db.delete(off)
            if 'fmt' in locals(): 
                # Need to delete sub-formation if Zonal Command created it (but we used State Command)
                db.delete(fmt)
            db.commit()
            print("Cleanup successful")
        except Exception as e:
            print(f"Cleanup failed: {e}")
        db.close()

if __name__ == "__main__":
    test_filters()
