from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..dependencies import require_admin
from ..models import User
from ..services.risk_scheduler import (
    start_scheduler,
    stop_scheduler,
    update_interval,
    get_status,
)

router = APIRouter(prefix="/risk/scheduler", tags=["RiskScheduler"])

class StartRequest(BaseModel):
    interval_seconds: int = 60

class IntervalPatch(BaseModel):
    interval_seconds: int

@router.get("/status", summary="查看调度器状态（管理员）")
def scheduler_status(admin: User = Depends(require_admin)):
    return get_status()

@router.post("/start", summary="启动调度器（管理员）")
def scheduler_start(body: StartRequest, admin: User = Depends(require_admin)):
    ok = start_scheduler(body.interval_seconds)
    if not ok:
        raise HTTPException(status_code=400, detail="调度器已在运行")
    return {"started": True, "status": get_status()}

@router.post("/stop", summary="停止调度器（管理员）")
def scheduler_stop(admin: User = Depends(require_admin)):
    ok = stop_scheduler()
    if not ok:
        raise HTTPException(status_code=400, detail="调度器未在运行")
    return {"stopped": True, "status": get_status()}

@router.patch("/config", summary="更新调度间隔（管理员）")
def scheduler_update_interval(body: IntervalPatch, admin: User = Depends(require_admin)):
    try:
        update_interval(body.interval_seconds)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"updated": True, "status": get_status()}