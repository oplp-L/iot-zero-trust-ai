RISK_DEFAULT_CONFIG = {
    "thresholds": {
        # 分数 < low => low;  low <= 分数 < high => medium; >= high => high
        "low": 30,
        "high": 60,
    },
    "weights": {
        # 各指标命中就加权（可调）
        "auth_fail_rate": 25,
        "policy_violation": 17,
        "flow_spike_first": 20,
        "new_protocol": 10,
        "command_anomaly": 24,
    },
    "flow_spike": {
        # 流量峰值阈值（bytes_out）
        "threshold": 20000
    },
    "auth_fail": {
        # 认证失败率阈值
        "fail_rate_threshold": 0.5
    },
    "command": {"sensitive_cmds": ["reboot", "factory_reset", "wipe", "reset"]},
    "auto_response": {
        "isolate": {"high": True},
        "restore": {
            "enabled": True,
            "min_consecutive_non_high": 2,
            "lookback_scores": 5,
            "cooldown_seconds": 10,  # 测试用，正式可改 60
            "allow_levels": ["low", "medium"],
        },
    },
}
