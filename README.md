# IoT Zero Trust AI

面向物联网的零信任与风险评估演示项目。后端基于 FastAPI + SQLAlchemy，支持：
- 用户认证（OAuth2 + JWT）
- 设备管理（创建设备、查询、删除）
- 设备事件采集（单条/批量）
- 风险评估与自动处置（命中阈值自动记录“隔离”动作）
- Docker 一键运行，附带测试容器
- Swagger/OpenAPI 文档：/docs

> 前端说明请见 [frontend/README.md](frontend/README.md)。本文件主要说明项目总体与后端的运行、演示与交付事项。

## 目录结构

```text
.
├─ backend/                 # 后端源码（FastAPI）
│  └─ app/
│     ├─ main.py            # FastAPI 入口
│     ├─ auth.py            # 认证/JWT
│     ├─ db.py              # 数据库会话（已默认持久化到 /data）
│     ├─ models.py          # ORM 模型（用户、设备、事件、风险、动作等）
│     └─ routers/           # 路由（用户、设备、事件、风险）
├─ tests/                   # 后端测试
├─ scripts/
│  └─ demo.ps1              # 一键演示脚本（Windows PowerShell）
├─ docker-compose.yml
├─ Dockerfile
├─ .env.example             # 环境变量示例（复制为 .env 使用）
└─ README.md                # 本文档
```

## 快速开始（Docker 推荐）

1) 准备环境变量
```bash
# Linux/macOS
cp .env.example .env
# Windows PowerShell（生成随机 SECRET_KEY）：
# echo "SECRET_KEY=$(New-Guid)" | Out-File -Encoding UTF8 .env
```

2) 启动服务
```bash
docker compose up -d --build
# 看到 iot-zt-ai-api Up 且端口 8000 映射成功即可
```

3) 打开 API 文档
- http://127.0.0.1:8000/docs

4) 数据持久化
- SQLite 默认写入容器的 /data，已通过 docker-compose 映射到宿主机 ./data 目录。
- 目录 data/ 已在 .gitignore 中忽略，避免提交本地数据。

## 一键演示（评委现场建议）

Windows PowerShell 运行脚本即可完成整套演示（创建 admin、登录、创建设备、写入 5 条 auth_fail 事件、触发高风险并查看处置动作）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo.ps1
```

预期输出：
- 风险评估返回 level = "high"
- /risk/actions/{device_id} 中出现 action_type = "isolate" 的动作记录

也可在 /docs 页面手动按 API 顺序操作。

## 环境变量

参考 [.env.example](./.env.example)：
- SECRET_KEY：JWT 签名密钥（必须设置为复杂随机值）
- SQLALCHEMY_DATABASE_URL：数据库连接串（默认 sqlite:////data/iot_zt_ai.db）
- UVICORN_HOST / UVICORN_PORT：服务监听地址与端口（默认 0.0.0.0:8000）

## 本地开发（非 Docker）

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install -r backend/requirements.txt
export SQLALCHEMY_DATABASE_URL="sqlite:///./data/iot_zt_ai.db"  # Windows 可写为 set 或 $env:
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## 测试

Compose 已包含 test 服务，会在容器内运行“稳定测试集”。查看日志：
```bash
docker logs -f iot-zt-ai-test
```

本地运行（可选）：
```bash
pip install -r backend/requirements.txt
python -m pytest -q tests/test_devices_delete.py tests/test_risk_engine_e2e.py -k "not test_restore_after_cooldown_and_low"
```

## 常见问题与排查

- 构建阶段卡在 docker/dockerfile:1 或拉取超时
  - 临时禁用 BuildKit（本地构建时）：
    - PowerShell: `$env:DOCKER_BUILDKIT="0"; docker compose build --no-cache`
  - 或在 Docker Desktop -> Settings -> Docker Engine 配置 registry-mirrors（如 USTC、Baidu 等）后 Apply & Restart 再构建。

- 仍然报 IPv6 地址超时（dial tcp [xxxx]:443）
  - 切换到 IPv4 可用网络（热点/家庭网络），或临时禁用 IPv6，或配置公司代理。
  - 连通性测试（Windows PowerShell）：
    - `Test-NetConnection -ComputerName auth.docker.io -Port 443`
    - `Test-NetConnection -ComputerName registry-1.docker.io -Port 443`

- Compose 顶层 version 警告
  - 本仓库已去掉顶层 `version` 字段，使用 Compose v2 原生格式即可。

## 安全注意事项

- 生产环境务必设置强随机的 `SECRET_KEY` 并通过 `.env` 注入。
- 目前为演示方便，允许匿名创建用户；生产应改为仅管理员可创建。
- 建议开启 CORS 白名单、HTTPS 反向代理与访问控制日志审计。
- 数据库默认是 SQLite，建议按需切换到 PostgreSQL/MySQL 并做好备份策略。

## 许可证

TBD（如需开源可选择 MIT 或 Apache-2.0，并在仓库添加 LICENSE 文件）。