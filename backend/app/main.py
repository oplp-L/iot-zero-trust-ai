from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from .routers import device, device_events
import os
from .routers import risk_scheduler_admin
from backend.app.routers import risk_actions
from backend.app.routers import risk_actions_manual
from .models import Base
from .db import engine
from .routers import user, device, group, log, events, risk
from .routers import risk_config_admin  # 新增配置管理路由
from . import auth

# 数据表初始化
Base.metadata.create_all(bind=engine)

app = FastAPI(title="IoT Zero Trust AI Platform")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产可改为特定域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（注意：如果以后出现方法冲突，可调整顺序，把 risk_config_admin 放在 risk 之前）
app.include_router(user.router)
app.include_router(device.router)
app.include_router(device_events.router)
app.include_router(group.router)
app.include_router(log.router)
app.include_router(events.router)
app.include_router(risk.router)
app.include_router(risk_actions.router)
app.include_router(risk_actions_manual.router)
app.include_router(risk_config_admin.router)
app.include_router(risk_scheduler_admin.router)

@app.get("/")
def read_root():
    return {"msg": "IoT Zero Trust AI Platform backend is running!"}

@app.get("/me")
def read_me(current_user = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    }

# ===== 调试：列出当前进程路由 =====
BUILD_TAG = "risk-config-admin-debug-1"

@app.get("/__routes")
def list_routes():
    """
    调试端点：返回当前运行实例的所有已注册路由。
    用于确认真正监听中的进程加载了哪些方法（排查 405/404 时非常有用）。
    """
    data = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            data.append({
                "path": r.path,
                "methods": sorted(list(r.methods))
            })
    return {
        "build": BUILD_TAG,
        "pid": os.getpid(),
        "count": len(data),
        "routes": data
    }