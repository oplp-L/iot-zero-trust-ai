import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 优先读取环境变量；默认把 SQLite 放在容器 /data（compose 已映射到宿主机 ./data）
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:////data/iot_zt_ai.db")

# 只有 SQLite 才需要 check_same_thread=False
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)