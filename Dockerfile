# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off

WORKDIR /app

# 先复制依赖文件，利用缓存加速
COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-compile --upgrade pip && \
    if [ -f "/app/backend/requirements.txt" ]; then pip install -r /app/backend/requirements.txt; fi

# 复制源码（后端）与测试（方便容器内跑测试）
COPY backend /app/backend
COPY tests /app/tests

# 缺省环境变量（可由 compose/.env 覆盖）
ENV SQLALCHEMY_DATABASE_URL=sqlite:////data/iot_zt_ai.db \
    SECRET_KEY=changeme-in-prod \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

# 数据持久化目录（映射到宿主机）
RUN mkdir -p /data && chown -R root:root /data
VOLUME ["/data"]

EXPOSE 8000

# 启动 FastAPI（生产：无 --reload；开发要热重载可在 compose 命令里改）
CMD ["sh", "-c", "uvicorn backend.app.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT}"]