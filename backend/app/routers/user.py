from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from ..models import User
from .. import auth

router = APIRouter(prefix="/users", tags=["Users"])

# 使用统一的 DB 依赖
get_db = auth.get_db


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="user")


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existed = db.query(User).filter_by(username=user.username).first()
    if existed:
        # 幂等处理：若已存在，则将密码重置为新值（pbkdf2）并可同步更新角色，返回 200
        existed.password = auth.get_password_hash(user.password)
        if user.role:
            existed.role = user.role
        db.commit()
        db.refresh(existed)
        return {"id": existed.id, "username": existed.username, "role": existed.role}
    # 正常创建
    hashed = auth.get_password_hash(user.password)
    user_obj = User(username=user.username, password=hashed, role=user.role)
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    return {"id": user_obj.id, "username": user_obj.username, "role": user_obj.role}


@router.get("/")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]


# OAuth2 password grant 登录，返回 JWT
@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}