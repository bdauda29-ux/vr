from app.database import SessionLocal
from app.models import User, Formation
from app.auth import get_password_hash

db = SessionLocal()

# 1. Create vradmin user
username = "vradmin"
password = "vradmin123"
formation_id = 1

# Check if user exists
user = db.query(User).filter(User.username == username).first()
if not user:
    print(f"Creating user '{username}'...")
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        password_hash=hashed_password,
        role="formation_admin",
        formation_id=formation_id
    )
    db.add(user)
    db.commit()
    print(f"User '{username}' created successfully.")
else:
    print(f"User '{username}' already exists. Updating formation_id...")
    user.formation_id = formation_id
    user.role = "formation_admin"
    user.password_hash = get_password_hash(password) # Reset password just in case
    db.commit()
    print(f"User '{username}' updated.")

# Verify VR Formation exists
formation = db.query(Formation).filter(Formation.id == formation_id).first()
if formation:
    print(f"Formation ID {formation_id} is: {formation.name}")
else:
    print(f"Formation ID {formation_id} NOT FOUND!")

db.close()
