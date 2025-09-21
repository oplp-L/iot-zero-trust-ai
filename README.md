# IoT Zero Trust AI — 快速开始

## 运行（Docker Compose）
```bash
docker compose up -d
```

## 本地开发（后端）
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
pytest -q
uvicorn backend.app.main:app --reload
```

## 本地开发（前端）
```bash
cd frontend
cp .env.example .env
npm i
npm start
```

打开 http://localhost:3000 ，后端默认 http://localhost:8000

## 质量与安全
- Lint/格式: black, isort, flake8, mypy
- 测试: pytest + 覆盖率
- 安全: bandit, pip-audit, CodeQL
- 容器: hadolint, Trivy
- CI: GitHub Actions（PR 必跑）
- 分支保护: main 禁止强推/删除、要求 PR、要求状态检查通过

## 演示路径
1. 运行后端与前端
2. 前端仪表盘展示“后端可用路由/构建标签”
3. 使用脚本模拟事件，观察日志与数据库（如仓库的 demo 脚本）

## 生产化注意
- 将 SECRET_KEY、数据库凭据通过环境变量注入
- CORS 按域名收紧
- 如需并发/横向扩展，迁移到 PostgreSQL 并使用 Alembic 管理迁移