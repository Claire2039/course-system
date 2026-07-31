# 选课系统 (Course Registration System)

一个网页端学校选课系统，前后端分离、真实可用。详见 **[SPEC.md](./SPEC.md)**。

## 技术栈

- **前端**：Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query
- **后端**：FastAPI (async) + async SQLAlchemy + asyncpg
- **数据**：PostgreSQL（权威）+ Redis（快速门槛/限流/通知）+ MinIO（对象存储）
- **反代**：Caddy（自动 HTTPS）
- **实时**：SSE

## 快速开始

```bash
cp .env.example .env          # 按需修改密码/密钥
docker compose up -d --build  # 拉起全部 6 个服务
```

- 前端：http://localhost
- 后端健康检查：http://localhost/api/health
- MinIO 控制台：http://localhost:9001

> 本地默认走 HTTP（`:80`）。部署到真实域名时，把 `.env` 里 `SITE_ADDRESS` 改成域名，Caddy 会自动启用 HTTPS。

## 部署上线（分享给别人）

把系统部署到云服务器，拿到公网链接发给别人，对方用浏览器即可访问、**无需安装任何东西**。完整步骤见 **[DEPLOY.md](./DEPLOY.md)**（含阿里云：安全组、Docker 国内加速、2GB 加 swap、公网 IP HTTP、建表播种、压测演示）。压测脚本：`loadtest/locustfile.py`。

## 里程碑进度

| # | 里程碑 | 状态 |
|---|---|---|
| M0 | 脚手架 + 基础设施 | ✅ 完成 |
| M1 | 数据层（模型 + 迁移 + 种子） | ✅ 完成 |
| M2 | 认证（Session + 角色 + 批量导入） | ✅ 完成 |
| M3 | 目录浏览 API | ✅ 完成 |
| M4 | 选课引擎（FCFS + 防超卖 + 候补） | ✅ 完成 |
| M5 | 学生端前端 + 实时通知 | ✅ 完成 |
| M6 | 作业模块 | ✅ 完成 |
| M7 | 教师 & 管理员前端 | ✅ 完成 |
| M8 | 压测演示 + 上线 | ✅ 完成 |

> 登录、选课等功能在后续里程碑落地。

### 数据层初始化（M1）

```bash
docker compose up -d --build db api
docker compose exec api alembic upgrade head        # 建表
docker compose exec api python -m scripts.seed_data # 播种（幂等；--reset 强制重建）
```

- 演示登录：`admin@seed.example.com` / `Admin#2026`；学生/教师初始口令 `InitPass#2026`（首登强制改密）。
- `/health/ready` 现在会真实探测 DB：DB 不可达返回 **503**（不再是 200）。
- `scripts/seed_data.py` 位于 `backend/scripts/`（而非仓库根），以便随 api 镜像发布；SPEC §11 已同步。

## 架构图与完整设计

见 [SPEC.md](./SPEC.md)。
