import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSON_TYPE 必须加类型注解，否则 mypy 报 Cannot assign multiple types
try:
    from sqlalchemy import JSON as SA_JSON
except Exception:
    SA_JSON = None  # type: ignore

try:
    from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
except Exception:
    SQLITE_JSON = None  # type: ignore

# 先声明类型，再分支赋值，避免 mypy no-redef
JSON_TYPE: type
DB_DIALECT = os.getenv("DB_DIALECT", "sqlite").lower()
if DB_DIALECT == "sqlite" and SQLITE_JSON is not None:
    JSON_TYPE = SQLITE_JSON
elif SA_JSON is not None:
    JSON_TYPE = SA_JSON
else:
    JSON_TYPE = Text


# 新版推荐基类
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="owner")


class DeviceGroup(Base):
    __tablename__ = "device_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="normal")
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="group")


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="offline")
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("device_groups.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    is_isolated: Mapped[bool] = mapped_column(Boolean, default=False)
    owner: Mapped["User"] = relationship("User", back_populates="devices")
    group: Mapped["DeviceGroup"] = relationship("DeviceGroup", back_populates="devices")


class DeviceLog(Base):
    __tablename__ = "device_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    log_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    device: Mapped["Device"] = relationship("Device")


class DeviceEvent(Base):
    __tablename__ = "device_events"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False, default=lambda: datetime.now(UTC)
    )
    payload: Mapped[Any] = mapped_column(JSON_TYPE, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    device: Mapped["Device"] = relationship("Device", lazy="joined")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    level: Mapped[str] = mapped_column(String(10), index=True)
    reasons: Mapped[Any] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    device: Mapped["Device"] = relationship("Device", lazy="joined")


class RiskAction(Base):
    __tablename__ = "risk_actions"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    score_id: Mapped[int] = mapped_column(ForeignKey("risk_scores.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[Any] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    device: Mapped["Device"] = relationship("Device", lazy="joined")
    score: Mapped["RiskScore"] = relationship("RiskScore", lazy="joined")


class RiskConfigChange(Base):
    __tablename__ = "risk_config_changes"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=True)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    before_json: Mapped[Any] = mapped_column(JSON_TYPE)
    after_json: Mapped[Any] = mapped_column(JSON_TYPE)
    diff: Mapped[Any] = mapped_column(JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False, default=lambda: datetime.now(UTC)
    )
