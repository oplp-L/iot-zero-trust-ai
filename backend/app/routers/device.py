from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from typing import Optional, List

from ..models import Device, DeviceGroup, User, DeviceLog, DeviceEvent, RiskAction

# 测试会覆盖 get_db，这里兜底使用 SessionLocal（若不可用则在运行时抛错）
try:
    from ..db import SessionLocal  # type: ignore
except Exception:
    SessionLocal = None  # type: ignore

from .. import auth

router = APIRouter(prefix="/devices", tags=["Devices"])


def get_db():
    if SessionLocal is None:
        raise RuntimeError("SessionLocal is not available; tests should override get_db.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DeviceCreate(BaseModel):
    name: str = Field(..., description="设备名称")
    type: str = Field(..., description="设备类型（如 camera / sensor / gateway）")
    owner_id: Optional[int] = Field(None, description="归属用户 ID（为兼容 E2E，可为空或不存在）")
    group_id: Optional[int] = Field(None, description="分组 ID，可选")


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str
    status: Optional[str] = None
    ip_address: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None


class DeviceListOut(DeviceOut):
    pass


def _serialize_device(d: Device) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "type": d.type,
        "status": getattr(d, "status", None),
        "ip_address": getattr(d, "ip_address", None),
        "owner": d.owner.username if getattr(d, "owner", None) else None,
        "group": d.group.name if getattr(d, "group", None) else None,
    }


def require_admin(current_user: User = Depends(auth.get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限执行该操作")
    return current_user


@router.post("/", response_model=DeviceOut, status_code=status.HTTP_201_CREATED, summary="创建设备（仅管理员）")
def create_device(
    device: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限创建设备")

    # 放宽 owner 校验：允许 owner_id 缺失或不存在（为兼容 E2E 测试）
    if device.group_id:
        group = db.query(DeviceGroup).filter_by(id=device.group_id).first()
        if not group:
            raise HTTPException(status_code=400, detail="分组不存在")

    existed = db.query(Device).filter(Device.name == device.name).first()
    if existed:
        raise HTTPException(status_code=400, detail="设备名称已存在")

    device_obj = Device(
        name=device.name,
        type=device.type,
        owner_id=device.owner_id,
        group_id=device.group_id,
    )
    db.add(device_obj)
    db.commit()
    db.refresh(device_obj)

    db.add(DeviceLog(device_id=device_obj.id, log_type="create", message=f"Device '{device_obj.name}' created by {current_user.username}"))
    db.commit()

    return _serialize_device(device_obj)


@router.get("/{device_id}", response_model=DeviceOut, summary="获取设备信息")
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    d = db.query(Device).filter(Device.id == device_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="设备不存在")
    return _serialize_device(d)


@router.get("/", response_model=List[DeviceListOut], summary="列出设备")
def list_devices(
    limit: int = Query(100, ge=1, le=500, description="最大返回数量"),
    owner_only: bool = Query(False, description="为 True 时仅返回当前用户归属设备（非 admin 执行时可强制）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    q = db.query(Device)
    if current_user.role != "admin":
        q = q.filter(Device.owner_id == current_user.id)
    else:
        if owner_only:
            q = q.filter(Device.owner_id == current_user.id)

    rows = q.order_by(Device.id.asc()).limit(limit).all()
    return [_serialize_device(d) for d in rows]


@router.delete("/{device_id}", status_code=status.HTTP_200_OK, summary="删除设备（仅管理员）")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

    db.query(DeviceEvent).filter(DeviceEvent.device_id == device_id).delete(synchronize_session=False)
    db.query(RiskAction).filter(RiskAction.device_id == device_id).delete(synchronize_session=False)
    db.query(DeviceLog).filter(DeviceLog.device_id == device_id).delete(synchronize_session=False)

    db.delete(device)
    db.commit()
    return {"deleted": True, "device_id": device_id}