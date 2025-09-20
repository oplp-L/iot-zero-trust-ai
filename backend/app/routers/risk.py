from datetime import datetime, timedelta, UTC
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..models import User, Device, DeviceEvent, RiskAction

router = APIRouter(prefix="/risk", tags=["Risk"])

# 统一 DB 依赖
get_db = auth.get_db


def _check_device_permission(db: Session, current_user: User, device_id: int):
    # 最小实现：admin 放行；普通用户仅能访问自己拥有的设备
    if current_user.role == "admin":
        return
    owned = db.query(Device).filter_by(id=device_id, owner_id=current_user.id).first()
    if not owned:
        raise HTTPException(status_code=404, detail="Device not found or no permission")


@router.post("/evaluate/{device_id}")
def evaluate_device_risk_api(
    device_id: int,
    window: int = Query(5, ge=1, le=60, description="统计时间窗口（分钟）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    _check_device_permission(db, current_user, device_id)

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    since = datetime.now(UTC) - timedelta(minutes=window)
    events: List[DeviceEvent] = (
        db.query(DeviceEvent)
        .filter(DeviceEvent.device_id == device_id, DeviceEvent.ts >= since)
        .all()
    )

    auth_fail_count = sum(1 for e in events if (e.event_type or "").lower() == "auth_fail")
    level = "high" if auth_fail_count >= 5 else "low"

    # 当 high 时自动记录 isolate 动作，并可标记设备为隔离
    if level == "high":
        db.add(RiskAction(device_id=device_id, action_type="isolate", executed=True, detail={"reason": "auth_fail_threshold"}))
        device.is_isolated = True
        db.commit()

    return {
        "device_id": device_id,
        "window_minutes": window,
        "level": level,
        "counts": {"auth_fail": auth_fail_count, "total": len(events)},
    }


@router.get("/actions/{device_id}")
def list_actions(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    _check_device_permission(db, current_user, device_id)
    acts: List[RiskAction] = (
        db.query(RiskAction)
        .filter(RiskAction.device_id == device_id)
        .order_by(RiskAction.id.asc())
        .all()
    )
    return [
        {
            "id": a.id,
            "device_id": a.device_id,
            "action_type": a.action_type,
            "executed": a.executed,
            "detail": a.detail,
        }
        for a in acts
    ]