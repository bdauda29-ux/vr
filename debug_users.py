from app.database import SessionLocal
from app.models import User, Staff

db = SessionLocal()

print("--- Users with role 'formation_admin' ---")
users = db.query(User).filter(User.role == "formation_admin").all()
for u in users:
    print(f"Username: {u.username}, Role: {u.role}, Formation ID: {u.formation_id}")

print("\n--- Users with role 'special_admin' ---")
users = db.query(User).filter(User.role == "special_admin").all()
for u in users:
    print(f"Username: {u.username}, Role: {u.role}, Formation ID: {u.formation_id}")

print("\n--- VR Staff Count ---")
# Assuming VR is formation_id 1
count = db.query(Staff).filter(Staff.formation_id == 1).count()
print(f"Staff in Formation 1: {count}")

db.close()
