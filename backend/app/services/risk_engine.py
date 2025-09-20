"""
风险引擎 (统一评分 + 自动隔离 + 自动恢复)
"""

from __future__ import annotations

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, List, Optional, Set

from ..models import (
    DeviceEvent,
    RiskScore,
    DeviceLog,
    RiskAction,
)

# 使用你已有的动态配置加载器
from .risk_config import risk_config


def _to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    将传入 datetime 标准化为 UTC aware，保持语义不变：
    - None -> None
    - naive -> 视为 UTC（加 tzinfo=UTC）
    - aware -> 转为 UTC
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# ================== 可选：ML 占位 ==================
def run_ml_anomaly(features: dict) -> Optional[dict]:
    """
    占位：后续可接入 ML 模型（IsolationForest / AutoEncoder 等）
    返回示例: {"score": 0.73, "model": "iforest"}
    现在返回 None 表示未启用
    """
    return None


# ================== 内部状态/动作辅助函数 ==================
def _latest_isolation_or_restore(db: Session, device_id: int) -> Optional[RiskAction]:
    return (
        db.query(RiskAction)
        .filter(
            RiskAction.device_id == device_id,
            RiskAction.action_type.in_(["isolate", "restore"])
        )
        .order_by(RiskAction.id.desc())
        .first()
    )


def _is_device_isolated(db: Session, device_id: int) -> bool:
    act = _latest_isolation_or_restore(db, device_id)
    return bool(act and act.action_type == "isolate")


def _last_isolation_time(db: Session, device_id: int) -> Optional[datetime]:
    act = (
        db.query(RiskAction)
        .filter(
            RiskAction.device_id == device_id,
            RiskAction.action_type == "isolate"
        )
        .order_by(RiskAction.id.desc())
        .first()
    )
    return act.created_at if act else None


def _recent_scores(db: Session, device_id: int, limit: int) -> List[RiskScore]:
    return (
        db.query(RiskScore)
        .filter(RiskScore.device_id == device_id)
        .order_by(RiskScore.id.desc())
        .limit(limit)
        .all()
    )


# ================== 自动隔离 ==================
def maybe_auto_isolate(
    db: Session,
    risk_score: RiskScore,
    cfg: Dict[str, Any],
):
    """
    触发条件:
      - 当前评分等级为 high
      - 配置 auto_response.isolate.high = True
      - 当前尚未处于隔离状态
    """
    auto_cfg = cfg.get("auto_response", {})
    iso_cfg = auto_cfg.get("isolate", {}) if isinstance(auto_cfg, dict) else {}

    if risk_score.level != "high":
        return
    if not iso_cfg.get("high"):
        return
    if _is_device_isolated(db, risk_score.device_id):
        return

    action = RiskAction(
        device_id=risk_score.device_id,
        score_id=risk_score.id,
        action_type="isolate",
        executed=True,
        detail={
            "mode": "auto",
            "score": risk_score.score,
            "level": risk_score.level,
            "reasons": risk_score.reasons,
            "at": datetime.now(UTC).isoformat()
        }
    )
    db.add(action)
    db.add(DeviceLog(
        device_id=risk_score.device_id,
        log_type="risk_alert",
        message=f"Auto isolation applied score={risk_score.score} level={risk_score.level}"
    ))
    db.commit()


# ================== 自动恢复 ==================
def maybe_auto_restore(
    db: Session,
    cfg: Dict[str, Any],
    risk_score: RiskScore,
):
    """
    触发条件:
      - 当前设备已处于隔离状态
      - restore.enabled = True
      - 距离最新隔离动作 >= cooldown_seconds
      - 最近 lookback_scores 条评分中，最新连续 min_consecutive_non_high 条都属于 allow_levels
        (并且这些条目为最新的倒序序列)
    """
    auto_cfg = cfg.get("auto_response", {})
    restore_cfg = auto_cfg.get("restore", {}) if isinstance(auto_cfg, dict) else {}
    if not restore_cfg.get("enabled"):
        return

    device_id = risk_score.device_id
    if not _is_device_isolated(db, device_id):
        return

    allow_levels = set(restore_cfg.get("allow_levels", ["low", "medium"]))
    min_consecutive = restore_cfg.get("min_consecutive_non_high", 2)
    lookback = restore_cfg.get("lookback_scores", 5)
    cooldown_seconds = restore_cfg.get("cooldown_seconds", 60)

    last_iso = _last_isolation_time(db, device_id)
    last_iso = _to_utc_aware(last_iso)
    if not last_iso:
        return
    if datetime.now(UTC) - last_iso < timedelta(seconds=cooldown_seconds):
        return

    scores = _recent_scores(db, device_id, lookback)
    if len(scores) < min_consecutive:
        return

    latest_needed = scores[:min_consecutive]  # 已按 id desc
    if all(s.level in allow_levels for s in latest_needed):
        # 双检：防并发重复恢复
        if not _is_device_isolated(db, device_id):
            return
        action = RiskAction(
            device_id=device_id,
            score_id=risk_score.id,
            action_type="restore",
            executed=True,
            detail={
                "mode": "auto",
                "reason": f"{min_consecutive} consecutive non-high scores",
                "at": datetime.now(UTC).isoformat()
            }
        )
        db.add(action)
        db.add(DeviceLog(
            device_id=device_id,
            log_type="risk_restore",
            message=f"Auto restore triggered after {min_consecutive} non-high scores"
        ))
        db.commit()


# ================== 评分核心 (保留你原来的逻辑, 仅内联改造) ==================
def compute_risk_for_device(
    db: Session,
    device_id: int,
    window_minutes: int = 5
) -> RiskScore:
    """
    按指定窗口计算风险，写入 RiskScore，并执行自动隔离/恢复判定。
    """
    cfg = risk_config.get()
    W = cfg["weights"]
    T = cfg["thresholds"]
    level_cfg = cfg["score_levels"]

    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(minutes=window_minutes)

    events = db.query(DeviceEvent).filter(
        DeviceEvent.device_id == device_id,
        DeviceEvent.ts >= window_start,
        DeviceEvent.ts < window_end
    ).all()

    reasons: List[Dict[str, Any]] = []
    score = 0.0

    if events:
        auth_fail = sum(1 for e in events if e.event_type == "auth_fail")
        auth_ok = sum(1 for e in events if e.event_type == "auth_success")
        policy_viol = sum(1 for e in events if e.event_type == "policy_violation")
        net_flows = [e for e in events if e.event_type == "net_flow"]
        cmd_events = [e for e in events if e.event_type == "command"]

        # 1. 认证失败率
        total_auth = auth_fail + auth_ok
        if (total_auth >= T["auth_fail_min_total"] and
            auth_fail >= T["auth_fail_min_fail"]):
            fail_rate = auth_fail / total_auth if total_auth > 0 else 0
            if fail_rate >= T["auth_fail_rate_min"]:
                w = W["auth_fail_rate"]
                score += w
                reasons.append({
                    "metric": "auth_fail_rate",
                    "auth_fail": auth_fail,
                    "total_auth": total_auth,
                    "fail_rate": round(fail_rate, 3),
                    "weight": w
                })

        # 2. 策略违规 (叠加步进， capped)
        if policy_viol > 0:
            w = min(W["policy_violation_base"] + policy_viol * W["policy_violation_step"], 30)
            score += w
            reasons.append({
                "metric": "policy_violation",
                "count": policy_viol,
                "weight": w
            })

        # 3. 流量突增 (对比最近24h历史)
        def _bytes(e): return (e.payload or {}).get("bytes_out", 0)
        cur_vals = [_bytes(e) for e in net_flows if _bytes(e) > 0]

        day_ago = window_end - timedelta(hours=24)
        hist_flows = db.query(DeviceEvent).filter(
            DeviceEvent.device_id == device_id,
            DeviceEvent.event_type == "net_flow",
            DeviceEvent.ts >= day_ago,
            DeviceEvent.ts < window_start
        ).all()
        hist_vals = [_bytes(e) for e in hist_flows if _bytes(e) > 0]

        if cur_vals:
            cur_peak = max(cur_vals)
            hist_mean = (sum(hist_vals) / len(hist_vals)) if hist_vals else 0
            if hist_mean > 0 and cur_peak / hist_mean > T["flow_spike_ratio"] and cur_peak > T["flow_spike_min_bytes"]:
                w = W["flow_spike"]
                score += w
                reasons.append({
                    "metric": "flow_spike",
                    "peak": cur_peak,
                    "hist_mean": hist_mean,
                    "weight": w
                })
            elif hist_mean == 0 and cur_peak > T["flow_spike_first_min_bytes"]:
                w = W["flow_spike_first"]
                score += w
                reasons.append({
                    "metric": "flow_spike_first",
                    "peak": cur_peak,
                    "weight": w
                })

        # 4. 新协议
        hist_protocols = set(
            (e.payload or {}).get("protocol")
            for e in db.query(DeviceEvent).filter(
                DeviceEvent.device_id == device_id,
                DeviceEvent.event_type == "net_flow",
                DeviceEvent.ts < window_start
            )
            if (e.payload or {}).get("protocol")
        )
        new_protos = set(
            (e.payload or {}).get("protocol")
            for e in net_flows
            if (e.payload or {}).get("protocol") and (e.payload or {}).get("protocol") not in hist_protocols
        )
        if new_protos:
            w = W["new_protocol"]
            score += w
            reasons.append({
                "metric": "new_protocol",
                "protocols": list(new_protos),
                "weight": w
            })

        # 5. 命令异常
            # baseline 定义为常规命令集
        baseline_cmds = {"ls", "status"}
        anomal_cmds = [
            (e.payload or {}).get("cmd")
            for e in cmd_events
            if (e.payload or {}).get("cmd") and (e.payload or {}).get("cmd") not in baseline_cmds
        ]
        if anomal_cmds:
            w = min(
                W["command_anomaly_base"] + len(anomal_cmds) * W["command_anomaly_step"],
                W["command_anomaly_max"]
            )
            score += w
            reasons.append({
                "metric": "command_anomaly",
                "count": len(anomal_cmds),
                "cmds": anomal_cmds,
                "weight": w
            })

        # 6. ML (可选占位)
        ml_res = run_ml_anomaly({"device_id": device_id, "event_count": len(events)})
        if ml_res:
            ml_weight = 15 * ml_res.get("score", 0)
            score += ml_weight
            reasons.append({
                "metric": "ml_anomaly",
                "model": ml_res.get("model"),
                "raw_score": ml_res.get("score"),
                "weight": ml_weight
            })

    # 归一 & level 判定
    score = min(score, 100.0)
    level = "low"
    if score >= level_cfg["high"]:
        level = "high"
    elif score >= level_cfg["medium"]:
        level = "medium"

    # 写 RiskScore
    rs = RiskScore(
        device_id=device_id,
        window_start=window_start,
        window_end=window_end,
        score=score,
        level=level,
        reasons=reasons
    )
    db.add(rs)

    db.add(DeviceLog(
        device_id=device_id,
        log_type="risk_eval",
        message=f"Risk evaluated: score={score} level={level}"
    ))
    db.commit()
    db.refresh(rs)

    # 自动隔离 / 恢复
    try:
        maybe_auto_isolate(db, rs, cfg)
    except Exception as e:
        db.add(DeviceLog(
            device_id=device_id,
            log_type="risk_eval",
            message=f"Auto isolation error: {e}"
        ))
        db.commit()

    try:
        maybe_auto_restore(db, cfg, rs)
    except Exception as e:
        db.add(DeviceLog(
            device_id=device_id,
            log_type="risk_eval",
            message=f"Auto restore error: {e}"
        ))
        db.commit()

    return rs


# ================== 对外统一入口 ==================
def evaluate_device_risk(
    db: Session,
    device_id: int,
    window_minutes: int = 5
) -> RiskScore:
    """
    统一对外调用入口：
    - 调用 compute_risk_for_device
    - 若后续需要加缓存 / APM / 指标，可在这里封装
    """
    return compute_risk_for_device(db, device_id, window_minutes=window_minutes)