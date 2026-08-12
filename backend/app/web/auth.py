"""
Web authentication using cookies.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, Response, HTTPException
from jose import JWTError, jwt

from ..config import settings


COOKIE_NAME = "normoscan_auth"
COOKIE_MAX_AGE = 60 * 24 * 7  # 7 days


def create_auth_cookie(response: Response, token: str) -> None:
    """Set auth cookie in response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear auth cookie."""
    response.delete_cookie(key=COOKIE_NAME)


def get_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from cookie or Authorization header."""
    # First try cookie
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    
    # Then try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    
    return None


def get_current_user_web(request: Request):
    """Get current user from web session (cookie or header)."""
    from ..db import SessionLocal
    from ..models.user import User
    
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Store user info in request state for templates
        request.state.username = user.username
        request.state.role = user.role
        
        return user
    finally:
        db.close()
