import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import text, asc, desc
from sqlalchemy.orm import Session

from ..db import SessionLocal
from .. import auth
from ..models import DeviceLog, Device, DeviceGroup, User

# 环境变量：LOG_DEBUG=1 时打印调试
LOG_DEBUG = os.getenv("LOG_DEBUG") == "1"

router = APIRouter(prefix="/logs", tags=["Logs"])


# ---------------- DB Session ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Helpers ----------------
def _debug(msg: str):
    if LOG_DEBUG:
        print(f"[LOGS_DEBUG] {msg}")


def serialize_log(log: DeviceLog) -> Dict[str, Any]:
    """
    标准化日志对象 -> JSON 可序列化 dict
    """
    ts = getattr(log, "timestamp", None)
    if ts:
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        else:
            ts = str(ts).replace(" ", "T")
    return {
        "id": getattr(log, "id", None),
        "device_id": getattr(log, "device_id", None),
        "log_type": getattr(log, "log_type", None),
        "message": getattr(log, "message", None),
        "timestamp": ts,
    }


def _get_user_device_ids(db: Session, user: User) -> List[int]:
    """
    返回普通用户的设备 ID 列表；管理员返回 [] 表示不限制。
    """
    if user.role == "admin":
        return []
    return [d.id for d in db.query(Device).filter_by(owner_id=user.id).all()]


# ---------------- Recent Logs ----------------
@router.get("", summary="获取近期日志")                # /logs
@router.get("/", include_in_schema=False)             # /logs/ 兼容，避免 307
def recent_logs(
    limit: int = Query(50, ge=1, le=500),
    since: Optional[str] = Query(None, description="ISO8601 (e.g. 2025-09-16T12:30:00)"),
    log_type: Optional[str] = Query(None, description="按日志类型过滤"),
    search: Optional[str] = Query(None, description="消息模糊匹配 (ILIKE %...%)"),
    sort: str = Query("id", pattern="^(id|timestamp)$", description="排序字段"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    """
    返回近期日志（默认按 id desc）。支持：
    - 权限隔离：非 admin 仅看自己设备；没有设备 -> []
    - since 时间过滤
    - log_type 精确过滤
    - search 模糊匹配 message
    - sort + order 自定义排序
    """
    _debug(f"recent_logs user={current_user.username} role={current_user.role}")

    q = db.query(DeviceLog)

    if current_user.role != "admin":
        owned_ids = _get_user_device_ids(db, current_user)
        if not owned_ids:
            _debug("user has no devices -> return []")
            return []
        q = q.filter(DeviceLog.device_id.in_(owned_ids))
        _debug(f"restrict device_ids={owned_ids}")

    if since:
        try:
            dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' format, require ISO8601")
        q = q.filter(DeviceLog.timestamp >= dt)

    if log_type:
        q = q.filter(DeviceLog.log_type == log_type)

    if search:
        like = f"%{search}%"
        q = q.filter(DeviceLog.message.ilike(like))

    col = DeviceLog.id if sort == "id" else DeviceLog.timestamp
    col = desc(col) if order == "desc" else asc(col)
    q = q.order_by(col)

    rows = q.limit(limit).all()
    return [serialize_log(r) for r in rows]


# ---------------- Device Logs ----------------
@router.get("/devices/{device_id}", summary="查看某设备日志")
def device_logs(
    device_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    if current_user.role != "admin":
        owned = db.query(Device).filter_by(id=device_id, owner_id=current_user.id).first()
        if not owned:
            raise HTTPException(status_code=404, detail="Device not found or no permission")

    rows = (
        db.query(DeviceLog)
        .filter(DeviceLog.device_id == device_id)
        .order_by(DeviceLog.id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_log(r) for r in rows]


# ---------------- Group Logs ----------------
@router.get("/groups/{group_id}", summary="查看某分组下设备日志")
def group_logs(
    group_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    group = db.query(DeviceGroup).filter_by(id=group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group_dev_ids = [d.id for d in group.devices]
    if not group_dev_ids:
        return []

    base_q = db.query(DeviceLog).join(Device, Device.id == DeviceLog.device_id)

    if current_user.role != "admin":
        owned_ids = [d.id for d in db.query(Device).filter_by(owner_id=current_user.id).all()]
        visible = list(set(owned_ids) & set(group_dev_ids))
        if not visible:
            return []
        base_q = base_q.filter(DeviceLog.device_id.in_(visible))
    else:
        base_q = base_q.filter(DeviceLog.device_id.in_(group_dev_ids))

    rows = base_q.order_by(DeviceLog.id.desc()).limit(limit).all()
    return [serialize_log(r) for r in rows]


# ---------------- Raw Basic (Admin) ----------------
@router.get("/raw/basic", summary="(Admin) 原始 SQL 调试")
def raw_basic(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    stmt = text("""
        SELECT id, device_id, log_type, message, timestamp
        FROM device_logs
        ORDER BY id DESC
        LIMIT :limit
    """)
    try:
        rows = db.execute(stmt, {"limit": limit}).fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Raw query failed: {e}")

    out = []
    for r in rows:
        m = r._mapping
        ts = m.get("timestamp")
        if ts:
            if hasattr(ts, "isoformat"):
                ts = ts.isoformat()
            else:
                ts = str(ts).replace(" ", "T")
        out.append({
            "id": m.get("id"),
            "device_id": m.get("device_id"),
            "log_type": m.get("log_type"),
            "message": m.get("message"),
            "timestamp": ts,
        })
    return out


# ---------------- 兼容旧 /_raw (Admin) ----------------
@router.get("/_raw", summary="(Admin) 兼容旧端点", include_in_schema=False)
def raw_compat(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    return raw_basic(limit=limit, db=db, current_user=current_user)