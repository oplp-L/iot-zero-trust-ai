from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventIngestItem(BaseModel):
    """
    单条设备事件写入模型
    ts 可选：如果不提供由后端补当前时间
    payload 为事件附加字段（协议、字节数、命令等）
    """

    device_id: int
    event_type: str = Field(
        ..., examples=["net_flow", "auth_fail", "auth_success", "command", "policy_violation"]
    )
    ts: Optional[datetime] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventIngestBatch(BaseModel):
    """
    批量事件写入
    """

    events: List[EventIngestItem]


class RiskReason(BaseModel):
    """
    评分原因统一结构（动态字段仍允许）
    metric: 指标名称，如 auth_fail_rate / policy_violation / flow_spike_first ...
    其余字段为该指标的上下文信息
    """

    metric: str
    # 允许动态扩展：其它键值放在 extra_fields，中转方式（简单起见直接 reasons 用 Dict[str,Any] 列表）
    # 若未来希望强约束，可为每种 metric 建独立模型。


class RiskScoreOut(BaseModel):
    """
    /risk/evaluate/{device_id} 返回
    """

    model_config = ConfigDict(from_attributes=True)

    device_id: int
    score: float
    level: str
    reasons: List[Dict[str, Any]] = Field(default_factory=list)
    window_start: datetime
    window_end: datetime


class RiskConfigOut(BaseModel):
    """
    /risk/config 返回
    注意：
      - weights / thresholds / score_levels 里既可能是 int 也可能是 float
      - auto_response 结构：
          {
            "isolate": { "high": true },
            "restore": {
                "enabled": true,
                "min_consecutive_non_high": 2,
                "lookback_scores": 5,
                "cooldown_seconds": 600,
                "allow_levels": ["low","medium"]
            }
          }
      - 未来扩展字段不会导致解析失败
    """

    model_config = ConfigDict(extra="allow")

    weights: Dict[str, Any]
    thresholds: Dict[str, Any]
    score_levels: Dict[str, Any]
    auto_response: Dict[str, Any]
