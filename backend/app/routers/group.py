from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..models import DeviceGroup, Device, User, DeviceLog
from ..db import SessionLocal
from .. import auth

router = APIRouter(prefix="/groups", tags=["Groups"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class GroupCreate(BaseModel):
    name: str
    description: str = ""


@router.post("/")
def create_group(
    group: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """
    创建分组：仅 admin
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限创建分组")

    if db.query(DeviceGroup).filter_by(name=group.name).first():
        raise HTTPException(status_code=400, detail="Group already exists")
    group_obj = DeviceGroup(name=group.name, description=group.description, status="normal")
    db.add(group_obj)
    db.commit()
    db.refresh(group_obj)

    # 日志（分组本身没有 device_id，这里不记录到 DeviceLog；也可扩展 SystemLog 表）
    return {
        "id": group_obj.id,
        "name": group_obj.name,
        "description": group_obj.description,
        "status": group_obj.status,
    }


@router.get("/")
def list_groups(db: Session = Depends(get_db)):
    """
    列出分组：公开只读（也可改为需要登录）
    """
    groups = db.query(DeviceGroup).all()
    return [
        {"id": g.id, "name": g.name, "description": g.description, "status": g.status}
        for g in groups
    ]


@router.post("/{group_id}/isolate")
def isolate_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """
    隔离分组：仅 admin
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限隔离分组")

    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.status == "isolate":
        return {"msg": "分组已隔离", "status": group.status}

    group.status = "isolate"
    devices = db.query(Device).filter_by(group_id=group_id).all()
    for d in devices:
        d.is_isolated = True
        d.status = "isolate"
        # 写设备日志
        db.add(
            DeviceLog(
                device_id=d.id,
                log_type="group_isolate",
                message=f"Device isolated via group '{group.name}' by {current_user.username}",
            )
        )
    db.commit()
    return {"msg": "分组隔离成功", "status": group.status, "affected_devices": len(devices)}


@router.post("/{group_id}/restore")
def restore_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """
    恢复分组：仅 admin
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限恢复分组")

    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.status == "normal":
        return {"msg": "分组状态已正常", "status": group.status}

    group.status = "normal"
    devices = db.query(Device).filter_by(group_id=group_id).all()
    for d in devices:
        d.is_isolated = False
        d.status = "online"
        # 写设备日志
        db.add(
            DeviceLog(
                device_id=d.id,
                log_type="group_restore",
                message=f"Device restored via group '{group.name}' by {current_user.username}",
            )
        )
    db.commit()
    return {"msg": "分组恢复成功", "status": group.status, "affected_devices": len(devices)}
