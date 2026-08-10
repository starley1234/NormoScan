from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from typing import Optional
from .config import settings
from .db import get_db
from .models.user import User, Role

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(pw: str) -> str:
    # bcrypt 72 bytes limit
    pw = pw[:72]
    return pwd_context.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    plain = plain[:72]
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta]=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = db.query(User).filter(User.username==username).first()
    if not user or not user.is_active:
        raise cred_exc
    return user

def get_current_user_optional(authorization: Optional[str] = Header(None), x_koseven_role: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # Support Koseven header passthrough
    if x_koseven_role and settings.koseven_enabled:
        # Map Koseven role to internal
        role_map = {"admin":"admin","normocontrol":"normocontroller","engineer":"engineer","user":"viewer"}
        # For demo, create ephemeral user
        u = User(username=f"koseven_{x_koseven_role}", role=role_map.get(x_koseven_role,"viewer"), hashed_password="*", is_active=True)
        u.id = -1
        return u
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ",1)[1]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        user = db.query(User).filter(User.username==username).first()
        return user
    except JWTError:
        return None

def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {roles}, got {user.role}")
        return user
    return checker

# RBAC permission matrix
PERMISSIONS = {
    "admin": ["*"],
    "normocontroller": ["check:create","check:read","check:feedback","gallery:write","gost:read","analytics:read","export"],
    "engineer": ["check:create","check:read","gost:read"],
    "viewer": ["check:read","gost:read"],
}

def has_permission(user: User, perm: str) -> bool:
    perms = PERMISSIONS.get(user.role, [])
    return "*" in perms or perm in perms
