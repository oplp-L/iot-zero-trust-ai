"""
风险动作逻辑 (auto isolation / auto restore 等)

现包含：
1. maybe_apply_auto_actions -> 自动隔离入口（保持旧调用兼容）
2. auto_isolation_process   -> 幂等自动隔离核心
3. maybe_auto_restore       -> 自动恢复（解除隔离）逻辑
4. _finalize_existing_isolation -> 兼容旧未执行 auto_isolate 记录

返回值约定：
- maybe_apply_auto_actions:
    "isolate" / "isolate(execute_pending)" / None
- maybe_auto_restore:
    "restore" / None

注意：
- 如果 Device 没有 status 字段，可将相关 status 操作块删除或注释。
- 依赖 risk_config 中 auto_response 配置，需已在 risk_config.py 中加入自动恢复相关字段：
    enable_restore, restore_low_level, restore_consecutive, restore_cooldown_minutes
"""

from __future__ import annotations
from typing import Optional, Union
from datetime import datetime, timedelta, UTC

from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models import RiskAction, RiskScore, DeviceLog, Device
from .risk_config import risk_config


def _to_utc_aware(dt: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """
    标准化时间为 UTC aware：
    - None -> None
    - str  -> 尝试 fromisoformat
    - naive datetime -> 视为 UTC
    - aware datetime -> 转 UTC
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return None


# ---------------------------------------------------------------------------
# 自动隔离入口（兼容旧调用）
# ---------------------------------------------------------------------------
def maybe_apply_auto_actions(db: Session, score: RiskScore) -> Optional[str]:
    """
    兼容旧版本的入口函数。外部调用保持不变。
    满足条件则执行自动隔离。
    """
    cfg = risk_config.get() or {}
    auto_cfg = cfg.get("auto_response", {})

    if not auto_cfg.get("enable_isolation"):
        return None
    if score.level != "high":
        return None
    if not auto_cfg.get("high_score_isolate"):
        return None

    return auto_isolation_process(db=db, score=score, config=cfg)


# ---------------------------------------------------------------------------
# 自动隔离核心逻辑
# ---------------------------------------------------------------------------
def auto_isolation_process(db: Session, score: RiskScore, config: dict) -> Optional[str]:
    """
    幂等自动隔离逻辑：
      1. 升级未执行的旧 auto_isolate
      2. 已 isolated 跳过
      3. 5 分钟内已有 isolate 跳过
      4. 创建 isolate 记录 + 更新设备状态 + 写日志
    """
    device_id = score.device_id
    device: Device | None = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        return None

    # 1. 兼容旧 pending
    pending = db.execute(text("""
        SELECT id FROM risk_actions
        WHERE device_id = :d
          AND action_type IN ('auto_isolate','isolate')
          AND (executed = 0 OR executed IS NULL)
        ORDER BY id DESC LIMIT 1
    """), {"d": device_id}).fetchone()
    if pending:
        _finalize_existing_isolation(db, device, pending.id, from_pending=True)
        return "isolate(execute_pending)"

    # 2. 已 isolated
    if hasattr(device, "status") and getattr(device, "status") == "isolated":
        return None

    # 3. 5 分钟内已隔离
    recent = db.execute(text("""
        SELECT id FROM risk_actions
        WHERE device_id=:d
          AND action_type='isolate'
          AND created_at >= datetime('now','-5 minutes')
        LIMIT 1
    """), {"d": device_id}).fetchone()
    if recent:
        return None

    # 4. 创建新动作
    reasons = getattr(score, "reasons", None)
    window_start = getattr(score, "window_start", None)
    window_end = getattr(score, "window_end", None)

    detail_payload = {
        "mode": "auto",
        "score": score.score,
        "level": score.level,
        "reasons": reasons,
        "window_start": window_start.isoformat() if hasattr(window_start, "isoformat") else str(window_start),
        "window_end": window_end.isoformat() if hasattr(window_end, "isoformat") else str(window_end),
    }

    action = RiskAction(
        device_id=device_id,
        score_id=score.id,
        action_type="isolate",
        executed=True,
        detail=detail_payload
    )
    db.add(action)

    if hasattr(device, "status"):
        try:
            device.status = "isolated"
        except Exception:
            pass

    db.add(DeviceLog(
        device_id=device_id,
        log_type="risk_alert",
        message=f"Auto isolation applied score={score.score} level={score.level}"
    ))
    db.commit()
    return "isolate"


# ---------------------------------------------------------------------------
# 自动恢复逻辑
# ---------------------------------------------------------------------------
def maybe_auto_restore(db: Session, score: RiskScore) -> Optional[str]:
    """
    检查并执行自动恢复：
      条件：
        - 配置 enable_restore=True
        - 设备当前 status='isolated'（若无该字段则跳过）
        - 最近 restore_consecutive 条 RiskScore（含当前）均为“低于 restore_low_level”
          * restore_low_level = "medium": 要求都是 low
          * restore_low_level = "high":   要求 low 或 medium
        - 距离最近一次 restore 动作 > restore_cooldown_minutes
    达成：
        - 创建 restore 动作
        - 设置 device.status='online'
        - risk_alert 日志
    幂等：
        - 冷却期内不重复
        - 1 分钟内已有新 restore 记录不重复
    """
    cfg = risk_config.get() or {}
    ar = cfg.get("auto_response", {})
    if not ar.get("enable_restore"):
        return None

    device: Device | None = db.query(Device).filter(Device.id == score.device_id).first()
    if not device:
        return None

    if not hasattr(device, "status"):
        return None
    if getattr(device, "status") != "isolated":
        return None

    restore_low_level = ar.get("restore_low_level", "medium")
    consecutive_need = ar.get("restore_consecutive", 3)
    cooldown_minutes = ar.get("restore_cooldown_minutes", 10)

    # 冷却检查
    last_restore = db.execute(text("""
        SELECT id, created_at FROM risk_actions
        WHERE device_id=:d AND action_type='restore'
        ORDER BY id DESC LIMIT 1
    """), {"d": device.id}).fetchone()
    if last_restore and last_restore.created_at:
        last_dt = _to_utc_aware(last_restore.created_at)
        if last_dt and (datetime.now(UTC) - last_dt) < timedelta(minutes=cooldown_minutes):
            return None

    # 最近 N 条风险记录
    recent_scores = (
        db.query(RiskScore)
        .filter(RiskScore.device_id == device.id)
        .order_by(RiskScore.id.desc())
        .limit(consecutive_need)
        .all()
    )
    if len(recent_scores) < consecutive_need:
        return None

    def low_enough(rs: RiskScore):
        if restore_low_level == "medium":
            return rs.level == "low"
        elif restore_low_level == "high":
            return rs.level in ("low", "medium")
        else:
            # 默认严格：按 medium 处理
            return rs.level == "low"

    if not all(low_enough(rs) for rs in recent_scores):
        return None

    # 1 分钟内已有 restore（极端并发防抖）
    very_recent = db.execute(text("""
        SELECT id FROM risk_actions
        WHERE device_id=:d AND action_type='restore'
          AND created_at >= datetime('now','-1 minutes')
        LIMIT 1
    """), {"d": device.id}).fetchone()
    if very_recent:
        return None

    # 执行恢复
    try:
        device.status = "online"
    except Exception:
        pass

    action = RiskAction(
        device_id=device.id,
        score_id=score.id,
        action_type="restore",
        executed=True,
        detail={
            "mode": "auto",
            "reason": "consecutive_low",
            "streak": consecutive_need,
            "levels": [rs.level for rs in recent_scores],
            "window_end": score.window_end.isoformat() if hasattr(score.window_end, "isoformat") else None
        }
    )
    db.add(action)
    db.add(DeviceLog(
        device_id=device.id,
        log_type="risk_alert",
        message=f"Auto restore applied (streak={consecutive_need})"
    ))
    db.commit()
    return "restore"


# ---------------------------------------------------------------------------
# 旧记录升级
# ---------------------------------------------------------------------------
def _finalize_existing_isolation(db: Session, device: Device, action_id: int, from_pending: bool = False) -> None:
    """
    将旧的 auto_isolate（未执行）补为已执行，并升级为 isolate。
    """
    db.execute(
        text("UPDATE risk_actions SET action_type='isolate', executed=1 WHERE id=:id"),
        {"id": action_id}
    )
    if hasattr(device, "status"):
        try:
            device.status = "isolated"
        except Exception:
            pass

    msg = "Previous pending auto_isolate executed" if from_pending else "Isolation finalized"
    db.add(DeviceLog(
        device_id=device.id,
        log_type="risk_alert",
        message=f"{msg} (action_id={action_id})"
    ))
    db.commit()