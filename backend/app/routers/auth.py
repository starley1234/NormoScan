from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import User
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterIn(BaseModel):
    username: str
    password: str
    email: str = None
    role: str = "engineer"

@router.post("/register")
def register(inp: RegisterIn, db: Session=Depends(get_db)):
    if db.query(User).filter(User.username==inp.username).first():
        raise HTTPException(400, "Username exists")
    # only admin can create admin/normocontroller? for demo allow
    u = User(username=inp.username, email=inp.email, hashed_password=hash_password(inp.password), role=inp.role, is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return {"id":u.id,"username":u.username,"role":u.role}

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session=Depends(get_db)):
    user = db.query(User).filter(User.username==form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type":"bearer", "role": user.role, "username": user.username}

@router.get("/me")
def me(user: User=Depends(get_current_user)):
    return {"id":user.id,"username":user.username,"role":user.role,"email":user.email}

# Seed admin if not exists
def seed_admin(db: Session):
    if not db.query(User).filter(User.username=="admin").first():
        u = User(username="admin", email="admin@normoscan.local", hashed_password=hash_password("admin123"), role="admin")
        db.add(u); db.commit()
    if not db.query(User).filter(User.username=="norm").first():
        u = User(username="norm", email="norm@normoscan.local", hashed_password=hash_password("norm123"), role="normocontroller")
        db.add(u); db.commit()
    if not db.query(User).filter(User.username=="engineer").first():
        u = User(username="engineer", email="eng@normoscan.local", hashed_password=hash_password("eng123"), role="engineer")
        db.add(u); db.commit()
