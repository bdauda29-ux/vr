from app.database import SessionLocal
from app import models

def check_staff():
    db = SessionLocal()
    try:
        count = db.query(models.Staff).count()
        print(f"Total Staff in DB: {count}")
        if count > 0:
            staff = db.query(models.Staff).first()
            print(f"First Staff: {staff.nis_no}, {staff.surname}")
            print(f"Password Hash: {staff.password_hash}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_staff()
