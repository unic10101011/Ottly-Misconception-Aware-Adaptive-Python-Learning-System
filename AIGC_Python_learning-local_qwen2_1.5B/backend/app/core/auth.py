import os
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User


ph = PasswordHasher()
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
bearer = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return ph.hash(password)


def auth_fingerprint(user: User) -> str:
    return hmac.new(SECRET_KEY.encode(), user.password.encode(), hashlib.sha256).hexdigest()[:16]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        user_id = payload.get("sub")
        if not user_id or not str(user_id).isdigit():
            raise JWTError("Missing subject")
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已失效") from None
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or user.status != "enabled" or not hmac.compare_digest(
        str(payload.get("v", "")), auth_fingerprint(user)
    ):
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user
