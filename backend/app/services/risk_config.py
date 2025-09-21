import json
import os
import threading
from typing import Any, Dict
import copy

"""
risk_config.py
统一管理风险引擎配置，支持：
1. 默认配置写入与自动创建 risk_config.json
2. 递归 schema 升级（新增字段自动补齐）
3. 向后兼容旧版 auto_response 扁平字段：
     旧:
       "auto_response": {
          "enable_isolation": True,
          "high_score_isolate": True,
          "enable_restore": True,
          "restore_low_level": "medium",
          "restore_consecutive": 3,
          "restore_cooldown_minutes": 10
       }
     新:
       "auto_response": {
          "isolate": { "high": True },
          "restore": {
              "enabled": True,
              "min_consecutive_non_high": 2,
              "lookback_scores": 5,
              "cooldown_seconds": 10,
              "allow_levels": ["low","medium"]
          }
       }
   在 load() 时会自动检测旧结构并迁移。
4. 线程安全 get / merge / replace
"""

# ========== 新版默认配置 ==========
_DEFAULT_CONFIG: Dict[str, Any] = {
    "weights": {
        "auth_fail_rate": 25,
        "policy_violation_base": 15,
        "policy_violation_step": 2,
        "flow_spike": 30,
        "flow_spike_first": 20,
        "new_protocol": 10,
        "command_anomaly_base": 20,
        "command_anomaly_step": 2,
        "command_anomaly_max": 35,
    },
    "thresholds": {
        "auth_fail_min_total": 5,
        "auth_fail_min_fail": 3,
        "auth_fail_rate_min": 0.6,
        "flow_spike_ratio": 3.0,
        "flow_spike_min_bytes": 5000,
        "flow_spike_first_min_bytes": 8000,
    },
    "score_levels": {"medium": 40, "high": 70},
    "auto_response": {
        "isolate": {
            # 是否对 high 等级自动隔离
            "high": True
        },
        "restore": {
            "enabled": True,
            # 最近连续多少条评分非 high 才触发恢复
            "min_consecutive_non_high": 2,
            # 在最近多少条评分中进行判定（窗口）
            "lookback_scores": 5,
            # 冷却时间（秒）（上一次 isolate 到现在 >= cooldown 才允许恢复）
            "cooldown_seconds": 600,  # 等价旧版 restore_cooldown_minutes=10
            # 哪些 level 计入“安全”或“可恢复”集合
            "allow_levels": ["low", "medium"],
        },
    },
}


class RiskConfig:
    """
    - 初次不存在: 写入默认
    - load 时自动补齐缺失字段
    - 自动从旧版 auto_response 扁平结构迁移到新版嵌套结构
    - 提供 merge 与 replace_and_persist
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self.load()

    # ---------------- Public API ----------------
    def get(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)

    def load(self):
        with self._lock:
            if os.path.isfile(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                except Exception:
                    self._data = copy.deepcopy(_DEFAULT_CONFIG)
            else:
                self._data = copy.deepcopy(_DEFAULT_CONFIG)
                self._save_unlocked()

            # 升级 schema（补缺字段）
            if self._upgrade_schema(self._data, _DEFAULT_CONFIG):
                self._save_unlocked()

            # 旧结构向后兼容转换
            if self._maybe_migrate_legacy_auto_response(self._data):
                self._save_unlocked()

    def reload(self):
        self.load()

    def merge(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归 merge 后持久化，返回新的深拷贝
        （审计由上层服务控制，这里只做数据操作）
        """
        with self._lock:

            def _merge(a, b):
                for k, v in b.items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        _merge(a[k], v)
                    else:
                        a[k] = copy.deepcopy(v)

            _merge(self._data, patch)
            if self._maybe_migrate_legacy_auto_response(self._data):
                # 若用户通过 patch 又打回旧结构，强制迁回新结构
                pass
            self._save_unlocked()
            return copy.deepcopy(self._data)

    def replace_and_persist(self, new_cfg: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._data = copy.deepcopy(new_cfg)
            # 替换后同样确保 schema & 迁移一致
            changed_schema = self._upgrade_schema(self._data, _DEFAULT_CONFIG)
            changed_migrate = self._maybe_migrate_legacy_auto_response(self._data)
            if changed_schema or changed_migrate:
                pass
            self._save_unlocked()
            return copy.deepcopy(self._data)

    # ---------------- Internal helpers ----------------
    def _save_unlocked(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            # 静默：可按需改为日志
            pass

    def _upgrade_schema(self, current: Dict[str, Any], default: Dict[str, Any]) -> bool:
        """
        递归补齐缺失字段；不覆盖已有值
        """
        changed = False
        for k, v in default.items():
            if k not in current:
                current[k] = copy.deepcopy(v)
                changed = True
            else:
                if isinstance(v, dict) and isinstance(current[k], dict):
                    if self._upgrade_schema(current[k], v):
                        changed = True
        return changed

    def _maybe_migrate_legacy_auto_response(self, cfg: Dict[str, Any]) -> bool:
        """
        将旧版扁平 auto_response 结构迁移为新版嵌套结构
        旧:
            {
              "enable_isolation": True,
              "high_score_isolate": True,
              "enable_restore": True,
              "restore_low_level": "medium",
              "restore_consecutive": 3,
              "restore_cooldown_minutes": 10
            }
        新:
            {
              "isolate": { "high": True },
              "restore": {
                 "enabled": True,
                 "min_consecutive_non_high": 2,
                 "lookback_scores": 5,
                 "cooldown_seconds": 600,
                 "allow_levels": ["low","medium"]
              }
            }
        迁移策略：
          - 如果已存在 isolate/restore 子结构则不动
          - 否则读取旧键生成新结构
        """
        changed = False
        ar = cfg.get("auto_response")
        if not isinstance(ar, dict):
            return False

        has_new = "isolate" in ar or "restore" in ar
        legacy_keys = {
            "enable_isolation",
            "high_score_isolate",
            "enable_restore",
            "restore_low_level",
            "restore_consecutive",
            "restore_cooldown_minutes",
        }
        has_legacy = any(k in ar for k in legacy_keys)

        if (not has_new) and has_legacy:
            # 构建新结构
            isolate_high = bool(
                ar.get("enable_isolation", True) and ar.get("high_score_isolate", True)
            )
            restore_enabled = bool(ar.get("enable_restore", True))

            # 恢复触发等级：旧字段 restore_low_level 表示低于该级别即可恢复，
            # 新设计是允许的非 high 集合；若 restore_low_level=medium -> allow = ["low","medium"]
            restore_low_level = ar.get("restore_low_level", "medium")
            allow_levels = ["low", "medium"]
            if restore_low_level == "low":
                allow_levels = ["low"]
            # restore_consecutive -> min_consecutive_non_high
            min_consec = int(ar.get("restore_consecutive", 2))
            # cooldown_minutes -> cooldown_seconds
            cooldown_sec = int(ar.get("restore_cooldown_minutes", 10)) * 60

            # 构造新结构
            new_ar = {
                "isolate": {"high": isolate_high},
                "restore": {
                    "enabled": restore_enabled,
                    "min_consecutive_non_high": min_consec,
                    "lookback_scores": 5,
                    "cooldown_seconds": cooldown_sec,
                    "allow_levels": allow_levels,
                },
            }
            cfg["auto_response"] = new_ar
            changed = True

        # 如果已经是新结构但缺失某些子字段，也补齐
        if "isolate" in ar and isinstance(ar["isolate"], dict):
            if "high" not in ar["isolate"]:
                ar["isolate"]["high"] = True
                changed = True

        if "restore" in ar and isinstance(ar["restore"], dict):
            restore_def = _DEFAULT_CONFIG["auto_response"]["restore"]
            for k, v in restore_def.items():
                if k not in ar["restore"]:
                    ar["restore"][k] = copy.deepcopy(v)
                    changed = True

        return changed


# ---------------- 初始化全局配置实例 ----------------

# risk_config.json 放在项目根目录（与 backend 同级）
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..")
)
CONFIG_PATH = os.getenv("RISK_CONFIG_PATH", os.path.join(PROJECT_ROOT, "risk_config.json"))

risk_config = RiskConfig(CONFIG_PATH)
