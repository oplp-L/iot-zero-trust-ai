# 风险评分与自动响应模型说明

## 1. 设计目标
- 统一设备行为事件的风险量化标准，输出连续风险评分（score）与离散风险等级（level）
- 支持权重、阈值、等级边界的动态配置
- 提供自动隔离 (auto isolate) 与自动恢复 (auto restore) 的闭环能力
- 可扩展：新增指标不破坏旧配置（schema 自动升级）

## 2. 评分输入事件类型
| 类型 | 示例字段 (payload) | 用途 |
|------|--------------------|------|
| auth_fail / auth_success | (无 / 成功标记) | 计算认证失败率 |
| policy_violation         | rule                | 违规策略计数 |
| net_flow                 | bytes_out, protocol | 流量突增 / 新协议识别 |
| command                  | cmd                 | 敏感命令异常 |

## 3. 配置结构（risk_config.json 核心字段）
```json
{
  "weights": {
    "auth_fail_rate": 25,
    "policy_violation_base": 15,
    "policy_violation_step": 2,
    "flow_spike": 30,
    "flow_spike_first": 20,
    "new_protocol": 10,
    "command_anomaly_base": 20,
    "command_anomaly_step": 2,
    "command_anomaly_max": 35
  },
  "thresholds": {
    "auth_fail_min_total": 5,
    "auth_fail_min_fail": 3,
    "auth_fail_rate_min": 0.6,
    "flow_spike_ratio": 3.0,
    "flow_spike_min_bytes": 5000,
    "flow_spike_first_min_bytes": 8000
  },
  "score_levels": {
    "medium": 40,
    "high": 70
  },
  "auto_response": {
    "isolate": { "high": true },
    "restore": {
      "enabled": true,
      "min_consecutive_non_high": 2,
      "lookback_scores": 5,
      "cooldown_seconds": 10,
      "allow_levels": ["low","medium"]
    }
  }
}
```

### 3.1 weights 说明
| 权重键 | 说明 |
|-------|------|
| auth_fail_rate | 认证失败率达到阈值后一次性加分 |
| policy_violation_base + step | 违规第 1 条加 base；后续每条加 step |
| flow_spike / flow_spike_first | 是否出现突发大流量；首次突增可用 first 权重 |
| new_protocol | 出现窗口内未见过的新协议（相对历史） |
| command_anomaly_* | 可叠加的敏感命令分：base + (n-1)*step，上限 command_anomaly_max |

### 3.2 thresholds 说明
| 阈值 | 逻辑 |
|------|------|
| auth_fail_min_total / auth_fail_min_fail / auth_fail_rate_min | 需同时满足“总尝试 ≥ min_total”与“失败次数 ≥ min_fail”且“失败率 ≥ rate_min” |
| flow_spike_ratio | bytes_out / 历史均值 ≥ ratio |
| flow_spike_min_bytes | 当前流量绝对值需 ≥ 该值 |
| flow_spike_first_min_bytes | 第一次突增的最低触发字节 |
| 其余 | 按需扩展 |

### 3.3 等级划分
```
score < medium         => low
medium ≤ score < high  => medium
score ≥ high           => high
```
（阈值来自 score_levels）

## 4. 评分流程（伪代码）
```
events = load_events(device_id, window_minutes)
score = 0
reasons = []

# 1) 认证失败率
if total_auth >= auth_fail_min_total and fail_auth >= auth_fail_min_fail:
    rate = fail_auth / total_auth
    if rate >= auth_fail_rate_min:
        score += weights.auth_fail_rate
        reasons += {metric:"auth_fail_rate", ...}

# 2) 策略违规
if policy_violation_count > 0:
    add = weights.policy_violation_base + (policy_violation_count - 1)*weights.policy_violation_step
    score += add
    reasons += {metric:"policy_violation", count:...}

# 3) 流量突增
if has_flow_spike:
    if is_first_spike: score += weights.flow_spike_first
    else: score += weights.flow_spike
    reasons += {metric:"flow_spike_first" or "flow_spike", peak:...}

# 4) 新协议
if new_protocols_found:
    score += weights.new_protocol
    reasons += {metric:"new_protocol", protocols:[...]}

# 5) 敏感命令
if command_anomaly_count > 0:
    add = min(weights.command_anomaly_base + (count-1)*weights.command_anomaly_step,
              weights.command_anomaly_max)
    score += add
    reasons += {metric:"command_anomaly", count:..., cmds:[...]}

# 6) 得出等级
if score >= high: level="high"
elif score >= medium: level="medium"
else: level="low"

persist_score(device_id, score, level, reasons)
maybe_auto_isolate(...)
maybe_auto_restore(...)
```

## 5. 自动隔离状态机

状态集合：`Normal` / `Isolated`  
事件触发：
| 条件 | 触发 | 进入状态 | 记录 |
|------|------|----------|------|
| level = high 且 auto_response.isolate.high = true | isolate 动作 | Isolated | risk_alert + actions.insert(isolate) |
| 在 Isolated 且满足恢复条件 | restore 动作 | Normal | risk_restore + actions.insert(restore) |

恢复条件拆解：
1. auto_response.restore.enabled = true  
2. 距离上一次 isolate 时间 ≥ cooldown_seconds  
3. 最近 lookback_scores 条记录里（或至少已有 min_consecutive_non_high 条最新评分）出现一个“从最新往回数的”连续片段，其长度 ≥ min_consecutive_non_high 且每条 level ∈ allow_levels（默认 low/medium）  
4. 最近一次评分本身必须非 high（即用户在正常状态下才恢复）

## 6. 你的验证案例（真实数据）
高风险评分：
- auth_fail_rate 25
- policy_violation 17
- flow_spike_first 20
- new_protocol 10
- command_anomaly 22
合计 94 → 触发 isolate  
等待窗口老化 + 两次 low → restore

## 7. 性能 & 数据存储建议
| 模块 | 建议 |
|------|------|
| events 表 | 为 device_id + ts 建联合索引 |
| scores 表 | 留存最近 N 条（lookback_scores 读取 O(N)） |
| actions 表 | 存 action_type, score_id, detail(JSON) |
| 日志 | 简单 text + 类型，可按设备分区 |

## 8. 调优策略
| 目标 | 调整建议 |
|------|----------|
| 减少误隔离（过敏） | 提高 high 阈值；降低某些权重；增加触发阈值（如 auth_fail_min_total） |
| 提高敏感性 | 降低高阈值；降低 flow_spike_ratio；增加权重 |
| 缩短隔离时间 | 减少 cooldown_seconds 或减少 min_consecutive_non_high |
| 避免频繁抖动 | 增大 min_consecutive_non_high；适度提高 high 阈值 |

## 9. 常见问题 (FAQ)
| 现象 | 原因 | 解决 |
|------|------|------|
| 一直 medium 不隔离 | 分数 < high | 调低 high 或增加事件/权重 |
| 恢复迟迟不触发 | cooldown_seconds 未过 或 连续次数不足 | 等待 / 调小 cooldown / 减少 min_consecutive_non_high |
| 评估分=0 | 窗口里无事件或不满足最小阈值 | 确认 window / 事件时间 |
| 无 isolate 动作 | level 不是 high 或 isolate 配置关闭 | 检查 auto_response.isolate.high |
| schema 缺字段 | risk_config.json 手改缺键 | reload 触发自动补齐或删文件重新生成 |

## 10. 扩展方向
- 秒级窗口（window_seconds）支持
- 附加“重试抖动”防止刚恢复立即再隔离
- 行为基线学习（自适应权重或阈值）
- 指标衰减模型（时间权重）

## 11. 变更记录 (建议维护)
| 日期 | 版本 | 说明 |
|------|------|------|
| 2025-09-18 | v1 | 初版：权重 + 自动隔离/恢复 |
| TBD | v1.1 | 增加 re-isolate 抖动控制 |
