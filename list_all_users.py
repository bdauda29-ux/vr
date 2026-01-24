from app.database import SessionLocal
from app.models import User

db = SessionLocal()

print("--- All Users ---")
users = db.query(User).all()
for u in users:
    print(f"Username: {u.username}, Role: {u.role}, Formation ID: {u.formation_id}")

db.close()
