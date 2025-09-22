from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import RiskConfigChange
from .risk_config import risk_config

# 允许增量修改的顶层键
ALLOWED_TOP_KEYS = {"weights", "thresholds", "score_levels", "auto_response"}

# （可选）自动响应策略允许的恢复级别
ALLOWED_RESTORE_LEVELS = {"medium", "high"}  # 如果以后支持 low, 在此补充


class ConfigValidationError(ValueError):
    """聚合多个配置校验错误后抛出"""

    pass


def compute_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    """
    生成递归字段差异:
    返回: { "path.sub": (old, new), ... }
    """
    diff: Dict[str, Tuple[Any, Any]] = {}

    def _walk(b, a, path=""):
        keys = set(b.keys()) | set(a.keys())
        for k in keys:
            nb = b.get(k, "__MISSING__")
            na = a.get(k, "__MISSING__")
            sub = f"{path}.{k}" if path else k
            if isinstance(nb, dict) and isinstance(na, dict):
                _walk(nb, na, sub)
            else:
                if nb != na:
                    diff[sub] = (
                        None if nb == "__MISSING__" else nb,
                        None if na == "__MISSING__" else na,
                    )

    _walk(before, after)
    return diff


def validate_patch(patch: Dict[str, Any]) -> bool:
    """
    基础合法性：顶层 key 受限，其它层级内容在合并后统一校验。
    """
    if not isinstance(patch, dict):
        raise ValueError("Patch 必须是对象(dict)")
    for k in patch.keys():
        if k not in ALLOWED_TOP_KEYS:
            raise ValueError(f"不允许修改的顶层键: {k}")
    return True


def _validate_full_config(cfg: Dict[str, Any]) -> None:
    """
    对完整配置做强校验。失败抛出 ConfigValidationError。
    这里的规则可按实际业务调整/扩展。
    """
    errors: List[str] = []

    # 1. 必需部分存在性
    for section in ["weights", "thresholds", "score_levels", "auto_response"]:
        if section not in cfg:
            errors.append(f"缺少必要配置块: {section}")

    if errors:
        raise ConfigValidationError("; ".join(errors))

    weights = cfg["weights"]
    thresholds = cfg["thresholds"]
    score_levels = cfg["score_levels"]
    auto_response = cfg["auto_response"]

    # 2. weights 校验：全部非负整数/数值
    if not isinstance(weights, dict):
        errors.append("weights 必须是对象")
    else:
        for k, v in weights.items():
            if not isinstance(v, (int, float)):
                errors.append(f"weights.{k} 必须为数值")
            elif v < 0:
                errors.append(f"weights.{k} 不能为负数")

    # 3. thresholds 校验
    if not isinstance(thresholds, dict):
        errors.append("thresholds 必须是对象")
    else:
        num_fields_positive_or_zero = [
            "auth_fail_min_total",
            "auth_fail_min_fail",
            "flow_spike_min_bytes",
            "flow_spike_first_min_bytes",
        ]
        for f in num_fields_positive_or_zero:
            if f in thresholds:
                v = thresholds[f]
                if not isinstance(v, (int, float)):
                    errors.append(f"thresholds.{f} 必须为数值")
                elif v < 0:
                    errors.append(f"thresholds.{f} 不能为负数")

        # 比率字段
        if "auth_fail_rate_min" in thresholds:
            v = thresholds["auth_fail_rate_min"]
            if not isinstance(v, (int, float)):
                errors.append("thresholds.auth_fail_rate_min 必须为数值")
            elif not (0 <= v <= 1):
                errors.append("thresholds.auth_fail_rate_min 必须在 [0,1] 区间")

        if "flow_spike_ratio" in thresholds:
            v = thresholds["flow_spike_ratio"]
            if not isinstance(v, (int, float)):
                errors.append("thresholds.flow_spike_ratio 必须为数值")
            elif v <= 1:
                errors.append("thresholds.flow_spike_ratio 必须 > 1")

        # 交叉约束
        if all(k in thresholds for k in ["auth_fail_min_total", "auth_fail_min_fail"]):
            if thresholds["auth_fail_min_total"] < thresholds["auth_fail_min_fail"]:
                errors.append(
                    "thresholds.auth_fail_min_total 必须 >= thresholds.auth_fail_min_fail"
                )

    # 4. score_levels 校验
    if not isinstance(score_levels, dict):
        errors.append("score_levels 必须是对象")
    else:
        for k, v in score_levels.items():
            if not isinstance(v, (int, float)):
                errors.append(f"score_levels.{k} 必须为数值")
            elif v < 0:
                errors.append(f"score_levels.{k} 不能为负数")

        if all(k in score_levels for k in ["medium", "high"]):
            if score_levels["medium"] >= score_levels["high"]:
                errors.append("score_levels.medium 必须 < score_levels.high")

    # 5. auto_response 校验
    if not isinstance(auto_response, dict):
        errors.append("auto_response 必须是对象")
    else:
        bool_fields = ["enable_isolation", "high_score_isolate", "enable_restore"]
        for bf in bool_fields:
            if bf in auto_response and not isinstance(auto_response[bf], bool):
                errors.append(f"auto_response.{bf} 必须为布尔值")

        if "restore_consecutive" in auto_response:
            v = auto_response["restore_consecutive"]
            if not isinstance(v, int):
                errors.append("auto_response.restore_consecutive 必须为整数")
            elif v < 1:
                errors.append("auto_response.restore_consecutive 必须 >= 1")

        if "restore_cooldown_minutes" in auto_response:
            v = auto_response["restore_cooldown_minutes"]
            if not isinstance(v, int):
                errors.append("auto_response.restore_cooldown_minutes 必须为整数")
            elif v < 1:
                errors.append("auto_response.restore_cooldown_minutes 必须 >= 1")

        if "restore_low_level" in auto_response:
            v = auto_response["restore_low_level"]
            if v not in ALLOWED_RESTORE_LEVELS:
                errors.append(
                    f"auto_response.restore_low_level 取值非法: {v} (允许: {', '.join(sorted(ALLOWED_RESTORE_LEVELS))})"
                )

    if errors:
        raise ConfigValidationError("; ".join(errors))


def apply_patch(db: Session, patch: Dict[str, Any], operator: Optional[str]):
    """
    应用增量补丁:
    1. 校验顶层 key 合法
    2. 深度 merge
    3. 校验完整配置合法性
    4. 计算 diff
    5. 持久化 & 记录审计
    """
    validate_patch(patch)

    before = risk_config.get()
    merged = copy.deepcopy(before)

    def _merge(a: Dict[str, Any], b: Dict[str, Any]):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                _merge(a[k], v)
            else:
                a[k] = copy.deepcopy(v)

    _merge(merged, patch)

    # 全量校验（防止写入非法组合）
    _validate_full_config(merged)

    diff = compute_diff(before, merged)
    if not diff:
        return {"changed": False, "diff": {}, "config": merged}

    # 持久化配置
    risk_config.replace_and_persist(merged)

    # 审计
    audit = RiskConfigChange(
        operator=operator, change_type="patch", before_json=before, after_json=merged, diff=diff
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return {"changed": True, "diff": diff, "config": merged, "change_id": audit.id}


def rollback_to(db: Session, change_id: int, operator: Optional[str]):
    """
    回滚到指定历史记录 after_json 的状态:
    1. 读取目标记录
    2. 计算当前 -> 目标 的 diff
    3. 校验目标配置合法（防止历史数据已过时不合法）
    4. 持久化 & 审计
    """
    target = db.query(RiskConfigChange).filter(RiskConfigChange.id == change_id).first()
    if not target:
        raise ValueError("指定版本不存在")

    current = risk_config.get()
    before = current
    after = target.after_json

    if not isinstance(after, dict):
        raise ValueError("历史记录格式异常（after_json 非对象）")

    # 回滚前对目标配置再做全量校验（防御性）
    _validate_full_config(after)

    diff = compute_diff(before, after)
    if not diff:
        return {"rolled": False, "diff": {}}

    new_cfg = risk_config.replace_and_persist(after)

    audit = RiskConfigChange(
        operator=operator, change_type="rollback", before_json=before, after_json=new_cfg, diff=diff
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return {"rolled": True, "diff": diff, "new_change_id": audit.id, "config": new_cfg}
