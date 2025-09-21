from fastapi import Depends, HTTPException
from . import auth
from .models import User


def require_admin(current_user: User = Depends(auth.get_current_user)):
    """
    通用管理员鉴权依赖。
    - 使用已有的 auth.get_current_user 获取当前用户
    - 校验 role == 'admin'
    - 失败抛 403
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user
