from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def _pw_bytes(plain: str) -> bytes:
    # bcrypt only considers the first 72 bytes; truncate explicitly so longer
    # passwords hash/verify deterministically instead of raising ValueError.
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_pw_bytes(plain), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
