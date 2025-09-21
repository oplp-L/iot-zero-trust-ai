import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from .routers import device
from .routers import user
from .routers import device_events
from .routers import risk

# 确保在应用加载时创建所有表（CI/全新环境必需）
from .models import Base
from .db import engine

# 健康检查路由
from .health import router as health_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="IoT Zero Trust AI Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请按需限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(user.router)
app.include_router(device.router)
app.include_router(device_events.router)
app.include_router(risk.router)
app.include_router(health_router)


@app.get("/")
def read_root():
    return {"msg": "IoT Zero Trust AI Platform backend is running!"}


BUILD_TAG = "risk-e2e-minimal-1"


@app.get("/__routes")
def list_routes():
    data = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            data.append({"path": r.path, "methods": sorted(list(r.methods))})
    return {"build": BUILD_TAG, "pid": os.getpid(), "count": len(data), "routes": data}
