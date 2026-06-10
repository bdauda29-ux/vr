from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt

# Config
SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_TO_A_VERY_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# Force bcrypt to use a backend that handles long passwords or just use pbkdf2_sha256 as fallback
# But wait, bcrypt has a 72 byte limit.
# The error "ValueError: password cannot be longer than 72 bytes" happens during init?
# It seems passlib is trying to detect bugs and failing.
# Let's switch to pbkdf2_sha256 which is safer/easier if bcrypt is acting up on Windows/this version.

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.JWTError:
        return None
