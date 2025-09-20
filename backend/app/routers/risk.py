from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..db import SessionLocal
from .. import auth
from ..models import User, Device, RiskScore
from ..schemas_ai import RiskScoreOut, RiskConfigOut
# 说明：
# 1) compute_risk_for_device 内部已负责：计算分数 + 写入 RiskScore + 写 DeviceLog + 自动隔离 maybe_apply_auto_actions + 自动恢复 maybe_auto_restore
# 2) 因此路由里不需要再次调用 maybe_apply_auto_actions，避免重复动作
from ..services.risk_engine import evaluate_device_risk  # 这是我们在 risk_engine.py 末尾新增的包装函数
from ..services.risk_config import risk_config

router = APIRouter(prefix="/risk", tags=["Risk"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _check_device_permission(db: Session, current_user: User, device_id: int):
    """
    简单的权限校验：
    - admin 放行
    - 普通用户只允许访问自己拥有的设备
    """
    if current_user.role == "admin":
        return
    owned = (
        db.query(Device)
        .filter_by(id=device_id, owner_id=current_user.id)
        .first()
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Device not found or no permission")


@router.post(
    "/evaluate/{device_id}",
    response_model=RiskScoreOut,
    summary="手动计算某设备风险"
)
def evaluate_device_risk_api(
    device_id: int,
    window: int = Query(5, ge=1, le=60, description="统计时间窗口（分钟）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    """
    手动触发一次风险评估。
    注意：
    - 实际计算 & 自动隔离 / 恢复逻辑已经在 services.risk_engine.evaluate_device_risk (包装 -> compute_risk_for_device) 内部完成
    - 这里不再重复调用 maybe_apply_auto_actions，避免重复动作
    """
    _check_device_permission(db, current_user, device_id)
    rs = evaluate_device_risk(db, device_id, window_minutes=window)

    return RiskScoreOut(
        device_id=device_id,
        score=rs.score,
        level=rs.level,
        reasons=rs.reasons or [],
        window_start=rs.window_start,
        window_end=rs.window_end
    )


@router.get("/history/{device_id}", summary="查看设备风险历史")
def risk_history(
    device_id: int,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    _check_device_permission(db, current_user, device_id)
    rows = (
        db.query(RiskScore)
        .filter(RiskScore.device_id == device_id)
        .order_by(RiskScore.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "level": r.level,
            "window_start": r.window_start,
            "window_end": r.window_end,
            "reasons": r.reasons
        } for r in rows
    ]


@router.get("/config", response_model=RiskConfigOut, summary="查看当前风险配置")
def get_config(
    current_user: User = Depends(auth.get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    data = risk_config.get()
    return RiskConfigOut(**data)


@router.post("/config/reload", summary="重新加载风险配置")
def reload_config(
    current_user: User = Depends(auth.get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    risk_config.reload()
    return {"reloaded": True}