import os
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any

from passlib.context import CryptContext
import jwt  # PyJWT
from jwt import ExpiredSignatureError, PyJWTError

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import User

"""
认证与授权模块
------------------------------------------------------------------
开发环境：
  - 可以直接使用默认 SECRET_KEY（会打印提醒），但建议尽快通过环境变量注入：
        set SECRET_KEY=your_long_random_string   (Windows PowerShell)
        export SECRET_KEY=your_long_random_string (Linux / macOS)

生产环境：
  - 必须使用高强度随机字符串做 SECRET_KEY（不少于 32 位）
  - 不要把真实的 SECRET_KEY 写进仓库
"""

# 固定密钥策略：优先读取环境变量，缺失时使用占位符（开发期允许）
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_TO_A_STRONG_SECRET")
if SECRET_KEY == "CHANGE_ME_TO_A_STRONG_SECRET":
    # 仅作为开发提示，不抛异常；生产环境务必修改
    print("[auth] WARNING: Using default insecure SECRET_KEY. Set environment variable SECRET_KEY in production!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 可按需调整或改为从环境变量读取

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 注意：这里必须与登录路由匹配，你的登录端点是 /users/token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")


# ----------------------------- 数据库依赖 ----------------------------- #
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------- 密码处理 ----------------------------- #
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ----------------------------- 认证流程 ----------------------------- #
def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter_by(username=username).first()
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user


# ----------------------------- Token 生成与解析 ----------------------------- #
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT：
    data: 会被整体复制并追加 exp / iat
    expires_delta: 可传自定义过期时间；不传则使用 ACCESS_TOKEN_EXPIRE_MINUTES
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": now
    })
    # PyJWT encode
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    解码并验证 JWT：
    - 过期抛 401 Token 已过期
    - 其他签名/格式错误抛 401 Token 无效
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 已过期")
    except PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")


# ----------------------------- FastAPI 依赖：获取当前用户 ----------------------------- #
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(token)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效，缺少 sub")
    user = db.query(User).filter_by(username=username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


# ----------------------------- 可选：生成带默认过期时间的帮助函数 ----------------------------- #
def create_user_access_token(username: str) -> str:
    """
    语法糖：按用户名快速生成访问 token
    """
    return create_access_token({"sub": username})