import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

# 仅保留“最小可运行/可测试”的依赖，避免导入不存在的路由模块导致 CI 失败
from .routers import device

app = FastAPI(title="IoT Zero Trust AI Platform")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产可改为特定域
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册最小路由（满足 tests 中对 /devices 的调用）
app.include_router(device.router)

@app.get("/")
def read_root():
    return {"msg": "IoT Zero Trust AI Platform backend is running!"}

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