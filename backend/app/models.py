import os
from datetime import datetime, UTC
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    Text,
    Float,
)
from sqlalchemy.orm import declarative_base, relationship

# 统一处理 JSON 列类型：
# - 默认在 SQLite（CI/本地测试）下使用 sqlite 方言的 JSON（兼容 json1）
# - 若通过环境变量 DB_DIALECT 设为非 sqlite（如 postgres/mysql），则尝试使用通用 JSON
try:
    from sqlalchemy import JSON as SA_JSON  # 通用 JSON（需要后端方言支持）
except Exception:  # 极端兜底
    SA_JSON = None  # type: ignore

try:
    from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
except Exception:
    SQLITE_JSON = None  # type: ignore

DB_DIALECT = os.getenv("DB_DIALECT", "sqlite").lower()
if DB_DIALECT == "sqlite" and SQLITE_JSON is not None:
    JSON_TYPE = SQLITE_JSON
else:
    JSON_TYPE = SA_JSON if SA_JSON is not None else Text  # 最后兜底 Text

Base = declarative_base()


# ---------------- 原有模型 ----------------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(32), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    role = Column(String(16), default="user")  # admin/user
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    devices = relationship("Device", back_populates="owner")


class DeviceGroup(Base):
    __tablename__ = "device_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True, nullable=False)
    description = Column(Text)
    status = Column(String(20), default="normal")  # 分组状态：normal / isolate / ...
    devices = relationship("Device", back_populates="group")


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    type = Column(String(32))
    status = Column(String(16), default="offline")  # online/offline/isolate
    ip_address = Column(String(64))
    owner_id = Column(Integer, ForeignKey("users.id"))
    group_id = Column(Integer, ForeignKey("device_groups.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    is_isolated = Column(Boolean, default=False)
    owner = relationship("User", back_populates="devices")
    group = relationship("DeviceGroup", back_populates="devices")


class DeviceLog(Base):
    __tablename__ = "device_logs"
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    log_type = Column(String(32))
    message = Column(Text)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    device = relationship("Device")


# ---------------- 新增：AI 行为 / 风险 模型 ----------------

class DeviceEvent(Base):
    __tablename__ = "device_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), index=True, nullable=False)
    event_type = Column(String(50), index=True, nullable=False)  # net_flow / auth_fail / command / policy_violation ...
    ts = Column(DateTime(timezone=True), index=True, nullable=False, default=lambda: datetime.now(UTC))
    payload = Column(JSON_TYPE, nullable=True)  # 原始事件数据
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    device = relationship("Device", lazy="joined")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), index=True, nullable=False)
    window_start = Column(DateTime(timezone=True), index=True, nullable=False)
    window_end = Column(DateTime(timezone=True), index=True, nullable=False)
    score = Column(Float, nullable=False)
    level = Column(String(10), index=True)  # low / medium / high
    reasons = Column(JSON_TYPE, nullable=True)  # JSON 列（原因列表）
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    device = relationship("Device", lazy="joined")


class RiskAction(Base):
    __tablename__ = "risk_actions"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), index=True, nullable=False)
    score_id = Column(Integer, ForeignKey("risk_scores.id"), nullable=True)
    action_type = Column(String(30), nullable=False)  # isolate / restore / ...
    executed = Column(Boolean, default=False)
    detail = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    device = relationship("Device", lazy="joined")
    score = relationship("RiskScore", lazy="joined")


# ---------------- 新增：配置变更审计模型 ----------------
class RiskConfigChange(Base):
    __tablename__ = "risk_config_changes"

    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(64), nullable=True)                 # 操作人（用户名）
    change_type = Column(String(32), nullable=False)             # patch / rollback
    before_json = Column(JSON_TYPE)                              # 变更前完整配置
    after_json = Column(JSON_TYPE)                               # 变更后完整配置
    diff = Column(JSON_TYPE)                                     # {"path": ["old","new"], ...}
    created_at = Column(DateTime(timezone=True), index=True, nullable=False, default=lambda: datetime.now(UTC))