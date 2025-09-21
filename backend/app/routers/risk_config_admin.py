from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db import SessionLocal
from backend.app.services.risk_config import risk_config
from backend.app.services.risk_config_service import apply_patch, rollback_to
from backend.app.models import RiskConfigChange
from backend.app import auth

router = APIRouter(prefix="/risk/config", tags=["risk-config"])


# ---------------------------
# 基础依赖
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user():
    return auth.get_current_user()


# 仅要求已登录（用于只读接口）
def require_authenticated(current_user=Depends(auth.get_current_user)):
    return current_user


# 仅 admin（用于修改类接口）
def require_admin(current_user=Depends(auth.get_current_user)):
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(403, "Admin only")
    return current_user


# ---------------------------
# 写操作：PATCH 增量更新
# ---------------------------
@router.patch("/", summary="增量更新配置 (递归 merge，仅管理员)")
def patch_config(
    payload: Dict[str, Any], db: Session = Depends(get_db), current_admin=Depends(require_admin)
):
    """
    递归 merge 传入的字段到现有配置。
    仅允许修改允许的顶层键（在 service 校验）。
    变更会写审计表并生成 change_id。
    """
    try:
        result = apply_patch(db, payload, operator=current_admin.username)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


# （可选别名：允许 /risk/config 不带末尾斜杠也能 PATCH）
@router.patch("", include_in_schema=False)
def patch_config_alias(
    payload: Dict[str, Any], db: Session = Depends(get_db), current_admin=Depends(require_admin)
):
    return patch_config(payload, db, current_admin)


# ---------------------------
# 历史记录（只读，可放开给所有登录用户；若只给 admin 则改依赖）
# ---------------------------
@router.get("/history", summary="配置变更历史（最新在前）")
def list_changes(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated),
):
    rows = db.query(RiskConfigChange).order_by(RiskConfigChange.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "operator": r.operator,
                "change_type": r.change_type,
                "diff": r.diff,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {"value": out, "Count": len(out)}


# ---------------------------
# 回滚（写操作，仅 admin）
# ---------------------------
@router.post("/rollback/{change_id}", summary="回滚到指定历史版本（仅管理员）")
def rollback(change_id: int, db: Session = Depends(get_db), current_admin=Depends(require_admin)):
    try:
        res = rollback_to(db, change_id, operator=current_admin.username)
        return res
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------
# 版本号接口：返回最新 change_id
# ---------------------------
@router.get("/version", summary="获取当前配置版本号（最新 change_id）")
def get_version(db: Session = Depends(get_db), current_user=Depends(require_authenticated)):
    latest_id = db.query(RiskConfigChange.id).order_by(RiskConfigChange.id.desc()).limit(1).scalar()
    return {"version": latest_id or 0}


# ---------------------------
# 获取完整配置（含 version）
# 若要限制仅 admin，把依赖改为 require_admin
# ---------------------------
@router.get("", summary="获取完整配置（含版本号）")
def get_full_config(db: Session = Depends(get_db), current_user=Depends(require_authenticated)):
    cfg = risk_config.get()
    latest_id = db.query(RiskConfigChange.id).order_by(RiskConfigChange.id.desc()).limit(1).scalar()
    return {"version": latest_id or 0, "config": cfg}
