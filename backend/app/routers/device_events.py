from datetime import datetime, UTC
from typing import Optional, List, Dict, Any, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy.orm import Session

from .. import auth
from ..models import Device, DeviceEvent, User

router = APIRouter(prefix="/devices", tags=["Device Events"])

# 统一 DB 依赖
get_db = auth.get_db

ALLOWED_EVENT_TYPES = {
    "auth_fail",
    "auth_success",
    "policy_violation",
    "net_flow",
    "command",
}


class DeviceEventIn(BaseModel):
    event_type: str = Field(..., description="事件类型")
    payload: Dict[str, Any] = Field(default_factory=dict, description="事件附加数据（JSON）")
    ts: Optional[datetime] = Field(None, description="可选自定义时间戳，不传为当前时间（UTC）")

    @field_validator("event_type", mode="before")
    def validate_event_type(cls, v):
        if v not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"event_type 不支持: {v}")
        return v


class EventsIn(BaseModel):
    events: List[DeviceEventIn]


class DeviceEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: int
    event_type: str
    ts: datetime
    payload: Dict[str, Any]


@router.post(
    "/{device_id}/events",
    summary="写入单条或多条设备事件",
    response_model=List[DeviceEventOut],
    status_code=status.HTTP_201_CREATED,
)
def add_events(
    device_id: int,
    body: Union[DeviceEventIn, EventsIn],
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 可选权限控制：普通用户只能写自己的设备事件（当前为最小实现，默认放行 admin；如需开启，取消注释）
    # if current_user.role != "admin" and dev.owner_id != current_user.id:
    #     raise HTTPException(status_code=403, detail="无权限")

    # 统一成列表
    events_in = [body] if isinstance(body, DeviceEventIn) else body.events

    rows: List[DeviceEvent] = []
    default_now = datetime.now(UTC)
    for e in events_in:
        ts = e.ts
        if ts is None:
            ts = default_now
        else:
            ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)

        row = DeviceEvent(
            device_id=device_id,
            event_type=e.event_type,
            payload=e.payload,
            ts=ts,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


@router.get("/{device_id}/events", summary="列出最近事件", response_model=List[DeviceEventOut])
def list_events(
    device_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    q = (
        db.query(DeviceEvent)
        .filter(DeviceEvent.device_id == device_id)
        .order_by(DeviceEvent.id.desc())
        .limit(limit)
    )
    return list(reversed(q.all()))  # 升序返回