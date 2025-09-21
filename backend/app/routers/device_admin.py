from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# 复用已有的 get_db：从同目录的 device 路由导入（你的项目里每个路由都有自己的 get_db）
from .device import get_db

# 鉴权依赖：假设 get_current_user 在 backend/app/auth.py 中
from ..auth import get_current_user

# 模型：按你的项目结构常见命名导入，如有差异可参考 device_events.py / risk_actions.py 的导入写法调整
from ..models import Device, DeviceEvent, RiskAction

router = APIRouter(prefix="/devices", tags=["devices"])


def require_admin(user=Depends(get_current_user)):
    """
    要求当前用户是 admin。兼容对象或字典两种返回类型。
    """
    role = getattr(user, "role", None)
    if role is None and isinstance(user, dict):
        role = user.get("role")

    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


@router.delete("/{device_id}", status_code=status.HTTP_200_OK)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
):
    """
    删除设备，并清理其相关事件与风险动作。
    返回删除结果 JSON。
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # 若数据库层未配置外键 ON DELETE CASCADE，则手动级联删除
    db.query(DeviceEvent).where(DeviceEvent.device_id == device_id).delete(
        synchronize_session=False
    )
    db.query(RiskAction).where(RiskAction.device_id == device_id).delete(synchronize_session=False)

    db.delete(device)
    db.commit()

    return {"deleted": True, "device_id": device_id}
