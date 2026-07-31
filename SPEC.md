# 选课系统 — 设计规格与实施计划 (SPEC)

> 状态：已与用户达成共识（2026-07-29）。本文是唯一事实来源，后续开发以本文为准；变更需同步更新本文。

---

## 1. 项目定位

- **性质**：个人作品集 / 毕设级项目，**必须真实可用**（真数据库、真登录、真实时、真能交作业、部署起来真有人能用）。
- **不为真实学校的万级并发做生产级压测与运维**——一人有限时间扛不住，也没必要。
- **"先进"的落地方式**：正确的现代架构 + 真实规模种子数据，把容量竞争 / 时间冲突 / 并发控制 / 候补流转**真实跑通并演示**。
- **模拟体量**：约 30 门课 / 2000 学生 / 容量受限的若干教学班，逻辑真实，负载不真打到千级。

---

## 2. 总体架构

**前后端分离 + 独立后端**。一个 `docker-compose` 产物，本地与线上同一份配置。

```
                        ┌───────────────────────────┐
                        │          Caddy             │  自动 HTTPS 反代
                        │  (反向代理 + TLS 终止)      │
                        └───────┬────────────┬───────┘
                                │            │
                  / (前端)      │            │  /api, /events (后端)
                                ▼            ▼
                      ┌──────────────┐  ┌────────────────────┐
                      │  Next.js SSR │  │   FastAPI (async)   │
                      │  (App Router)│  │  REST + SSE + 业务   │
                      └──────┬───────┘  └───┬──────┬──────┬───┘
                             │              │      │      │
                             │   httpOnly   │      │      │ pub/sub
                             │   Session ───┘      │      │
                             │  Cookie            │      │
                             │                    ▼      ▼
                             │              PostgreSQL  Redis
                             │              (权威数据)  (门槛/限流/通知)
                             │                              │
                             │                              ▼ SSE
                             └──────────────────── MinIO (对象存储: 作业文件)
```

| 层 | 选型 |
|---|---|
| 前端 | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query |
| 后端 | FastAPI (async) + async SQLAlchemy + asyncpg + Pydantic v2 |
| 数据库 | PostgreSQL（唯一事实来源） |
| 缓存/队列 | Redis（快速门槛 / 限流 / pub-sub 通知） |
| 对象存储 | MinIO（S3 兼容，存作业附件与提交文件） |
| 反向代理 | Caddy（自动 HTTPS） |
| 认证 | 服务端 Session（存 Redis）+ httpOnly Cookie + argon2 |
| 实时 | SSE（`sse-starlette`），后端订阅 Redis 每用户频道 |
| 类型契约 | FastAPI 自动生成 OpenAPI → `openapi-typescript` 生成前端 TS 类型与 API client |

---

## 3. 领域模型（数据结构）

### 3.1 实体关系（ERD 草图）

```
User ──(1:1)── Student
User ──(1:1)── Teacher
User.role ∈ {STUDENT, TEACHER, ADMIN}

Semester (is_current, enroll_open_at, enroll_close_at, drop_deadline, max_credits, max_courses)

Course ──(M:N 自引用)── CoursePrerequisite ──→ Course   (先修课)
Course ──(1:N)── Section ──(N:1)── Teacher
Section ──(1:N)── TimeSlot (day_of_week, start_period, end_period)
Section.seats_taken / capacity           ← 防超卖的核心字段

Enrollment (student, section, status, waitlist_position)   status ∈ {ENROLDED, WAITLISTED, DROPPED}

Section ──(1:N)── Assignment ──(1:N)── Submission ──(1:1)── Grade
                                                  └── file_key → MinIO

Notification (user, type, payload, read, created_at)
PeriodDef (period_no → start_time, end_time)   ← 钟点表，供课表显示
```

### 3.2 关键表与字段

- **users**: `id`, `email`(unique), `password_hash`, `role`, `name`, `must_change_password`, `created_at`
- **students**: `user_id`(PK/FK 1-1), `student_no`(unique), `grade`, `major`
- **teachers**: `user_id`(PK/FK 1-1), `teacher_no`(unique), `department`, `title`
- **semesters**: `id`, `name`, `is_current`, `enroll_open_at`, `enroll_close_at`, `drop_deadline`, `max_credits`, `max_courses`
- **period_defs**: `period_no`(PK), `start_time`, `end_time`
- **courses**: `id`, `code`(unique), `title`, `credits`, `description`, `department`
- **course_prerequisites**: `course_id`, `prereq_course_id` (复合主键)
- **sections**: `id`, `course_id`, `teacher_id`, `semester_id`, `capacity`, `seats_taken`(default 0), `room`
- **time_slots**: `id`, `section_id`, `day_of_week`(1-7), `start_period`, `end_period`
- **enrollments**: `id`, `student_id`, `section_id`, `status`, `waitlist_position`(nullable), `enrolled_at`, `updated_at`; 唯一约束 `(student_id, section_id)`
- **assignments**: `id`, `section_id`, `title`, `description`, `due_at`, `late_deadline`, `allow_late`, `attachment_key`
- **submissions**: `id`, `assignment_id`, `student_id`, `file_key`, `text_comment`, `submitted_at`, `status`(SUBMITTED/LATE); 唯一约束 `(assignment_id, student_id)`，重交即更新此行（最新为准）
- **grades**: `id`, `submission_id`(1-1), `score`, `feedback`, `graded_at`, `graded_by`
- **notifications**: `id`, `user_id`, `type`, `payload`(jsonb), `read`, `created_at`

### 3.3 Redis 结构

| Key | 用途 | 权威性 |
|---|---|---|
| `session:{sid}` | 登录会话 | 会话权威（可由 DB 重建用户身份） |
| `section:{id}:seats` | 容量快照（capacity / seats_taken） | **非权威**，仅做"满了就早拒绝"的快速门槛；以 DB 为准 |
| `ratelimit:enroll:{user_id}` | 选课限流（令牌桶） | — |
| `notify:ch:{user_id}` | pub/sub 频道，SSE 订阅 | — |

> **心法**：座位计数权威永远在 PostgreSQL，Redis 仅挡羊群 + 传话。Redis 不可信时回退到 DB 条件 UPDATE，仍零超卖。

---

## 4. 核心流程

### 4.1 选课（FCFS，整个系统的工程心脏）

一个 Postgres 事务内原子完成，**绝不超卖**：

```text
POST /api/v1/sections/{id}/enroll  (学生, 在选课窗口内)
├─ 0. 限流检查 (Redis ratelimit)；窗口外 → 403
├─ 1. Redis 快速门槛：若 section:{id}:seats 显示满 → 直接进候补分支（不查 DB）
├─ 2. BEGIN TX
│   ├─ 2a. 先修课校验：未满足 → ROLLBACK, 409
│   ├─ 2b. 学分/门数上限校验（本学期累计）→ 超限 ROLLBACK, 409
│   ├─ 2c. 时间冲突检测：查该生本学期 ENROLLED 的 sections 的 time_slots，
│   │        与目标 section 的 time_slots 比同日区间重叠 → 冲突 ROLLBACK, 409
│   ├─ 2d. 条件原子扣座：
│   │     UPDATE sections SET seats_taken = seats_taken + 1
│   │     WHERE id = :sid AND seats_taken < capacity
│   │     RETURNING seats_taken;
│   │     ── affected=1 → 建 ENROLLED 记录
│   │     ── affected=0 → 建 WAITLISTED 记录（position = 当前候补数+1）
│   └─ COMMIT
├─ 3. 写 Redis 快照（异步、允许失败）、发 pub/sub 通知
└─ 4. 返回 {status: ENROLLED | WAITLISTED, position?}
```

### 4.2 退课 + 候补自动顶上

```text
DELETE /api/v1/enrollments/{id}  (在退课截止前)
├─ BEGIN TX
│   ├─ 将该 enrollment 置 DROPPED；若曾 ENROLLED 则 seats_taken - 1
│   ├─ 取该 section 队首 WAITLISTED（按 position 升序）
│   ├─ 重新校验该候补生：时间冲突？学分上限？先修课？
│   │     ── 不满足 → 跳过他（置 DROPPED 并记录原因），顺延下一个（级联）
│   │     ── 满足 → 条件扣座成功 → 升为 ENROLLED
│   └─ COMMIT
└─ pub/sub 通知被顶上的学生「你已转正」(SSE)
```

> **M4 实现注记**：① 零超卖由条件 `UPDATE ... WHERE seats_taken < capacity RETURNING` 单一权威保证，READ COMMITTED 即可，不使用 `SELECT FOR UPDATE`（单行锁、无死锁）。② 候补位次 best-effort（并发下偶有重复），**FIFO 权威排序按 `(waitlist_position, id)`**（id 单调递增兜底）。③ 先修课"已满足"= 该生在任意学期有该先修课的 ENROLLED 记录（M4 代理；真实"已修过"以成绩判定留待 M6）。④ Redis 门槛/限流非权威，Redis 不可用时回退 DB 条件 UPDATE 仍零超卖。

### 4.3 认证

- 登录校验 argon2 → 创建 Session 存 Redis → 下发 httpOnly + SameSite Cookie。
- 首次登录（`must_change_password=true`）强制改密。
- 角色守卫：FastAPI 依赖注入 `require_role(STUDENT|TEACHER|ADMIN)`。
- 账号由 **ADMIN 批量导入**（CSV：角色/姓名/邮箱/学号或工号…），生成初始随机密码；**无公开注册**。

### 4.4 实时通知（SSE）

- `GET /api/v1/events`：长连接，后端订阅 `notify:ch:{user_id}`，把事件流推给浏览器 `EventSource`。
- 事件类型：抢满 / 候补位次变化 / 转正 / 退课成功 / 作业发布 / 临截止提醒 / 教师出分。
- 同一事件同时落库 `notifications` 表（刷新后仍可查看历史）。

### 4.5 作业

- **Assignment 挂 Section**，由该 section 的教师发布。
- 学生提交：上传文件 → MinIO（生成 `file_key`）+ 可选文字；**截止前可重交，最新为准**；超 `due_at` 但未过 `late_deadline` → `LATE`；过硬截止 → 拒收。
- 教师批改：打分 + 评语 → 写 `grades` → SSE 通知学生。

### 4.6 课表

- 周视图：`周一~周日 × 节次` 网格，按该生本学期 ENROLLED 的 sections + time_slots 汇总着色渲染。
- 数据来源：`me/schedule` = 该生当前学期所有 ENROLLED section 及其 time_slots。

---

## 5. API 清单（按模块）

**Auth**：`POST /auth/login` · `POST /auth/logout` · `GET /auth/me` · `POST /auth/change-password`

**Admin**：`POST /admin/import-users`(CSV) · `POST/GET/PATCH /admin/semesters`（含窗口配置）· CRUD `/admin/courses` · CRUD `/admin/sections` · `GET /admin/teachers`

**Catalog（全体可浏览）**：`GET /courses` · `GET /courses/{id}` · `GET /sections`(过滤: semester/course) · `GET /sections/{id}` · `GET /teachers` · `GET /teachers/{id}` · `GET /periods`(钟点表，供课表渲染)

**Enrollment（学生）**：`POST /sections/{id}/enroll` · `DELETE /enrollments/{id}` · `GET /me/enrollments` · `GET /me/schedule` · `GET /me/waitlist`

**Assignment / Submission**：
- 教师：`POST/GET /sections/{id}/assignments` · `GET /sections/{id}/submissions` · `POST /submissions/{id}/grade`
- 学生：`GET /me/assignments` · `POST /assignments/{id}/submit`(multipart→MinIO)

**Realtime**：`GET /events` (SSE)

**Teacher 工作台**：`GET /me/sections`(我教的教学班) · `GET /sections/{id}/roster`(花名册)

---

## 6. 前端「不同窗口」（三个角色 Dashboard）

- **学生**：课程目录浏览 / 选课（实时座位 & 候补位次）/ 我的课表（周视图）/ 我的候补 / 我的作业（提交 + 查分）/ 通知中心
- **教师**：我的教学班 / 花名册 / 布置作业 / 批改作业 / 通知
- **管理员**：目录管理（Course/Section/分教师/设容量时段）/ 批量导入用户 / 学期与选课窗口配置

---

## 7. 测试与「模拟」落地

| 类型 | 内容 |
|---|---|
| **pytest 单元/集成** | 时间冲突检测、候补顶上+级联跳过、座位扣减、限流 |
| **🎯 并发零超卖测试（镇店之宝）** | 对 `capacity=1` 的 section 并发发起 ~500 个 enroll，断言**恰好 1 个 ENROLLED、其余全 WAITLISTED、零超卖、无死锁** |
| **locust 压测脚本** | 模拟"窗口一开、2000 种子学生涌入抢课"，产出吞吐 / p95 / 零超卖报告——演示物 |
| **playwright E2E（stretch）** | 登录→选课→看课表→交作业 主流程 |

种子数据脚本 `scripts/seed_data.py`：一键生成 2000 学生 / 30 课程 / 若干 section / 教师账号 / ADMIN 账号 / 一个开启选课窗口的当前学期。

---

## 8. 部署

- **产物**：`docker-compose.yml` = `api`(FastAPI) + `web`(Next.js) + `db`(Postgres) + `cache`(Redis) + `minio`(MinIO) + `caddy`(反代)。
- **目标**：单台小 VPS（或 Fly.io / Railway），`docker compose up -d` 即上线，**出一个公开 HTTPS 演示链接**。
- Caddy 自动签发证书；`.env.example` 提供全部配置项。

---

## 9. Stretch（明确标注，MVP 不做）

- 批次 / 抽奖预分配阶段（意愿清单 → 算法分配 → FCFS 捡漏，模型已预留）
- 候补"确认窗口"
- 课表 `.ics` 导出
- 邮件 / 推送通知（MVP 仅 SSE 站内）

---

## 10. 实施里程碑

| # | 里程碑 | 产出 |
|---|---|---|
| **M0** | 脚手架 + 基础设施 | monorepo 结构 / `docker-compose.yml` 六服务跑通 + healthcheck / Caddy / `.env.example` / CI 雏形 |
| **M1** | 数据层 | SQLAlchemy 模型 + Alembic 迁移 + `seed_data.py` + PeriodDef |
| **M2** | 认证 | Session + argon2 + 角色守卫 + CSV 批量导入 + 首登强制改密 |
| **M3** | 目录浏览 API | courses / sections / teachers 查询接口 + OpenAPI → 前端类型生成 |
| **M4** | 选课引擎（核心） | FCFS 事务 + 防超卖 + 时间冲突 + 候补 FIFO+级联 + Redis 集成 + **并发零超卖测试** |
| **M5** | 学生端前端 + 实时 | 浏览/选课/课表/候补 + SSE 通知中心 |
| **M6** | 作业模块 | 布置 / MinIO 提交 / 重交 / 迟交 / 批改（前后端） |
| **M7** | 教师 & 管理员前端 | 教学班/花名册/批改；目录管理/批量导入/窗口配置 |
| **M8** | 演示与上线 | locust 压测脚本 + 部署 VPS + 公开链接 + README |
| *S* | *Stretch* | 批次抽奖 / .ics / 确认窗口 / playwright |

---

## 11. 仓库结构（规划）

```
选课系统/
├── SPEC.md                      # 本文件
├── README.md
├── docker-compose.yml
├── .env.example
├── caddy/Caddyfile
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                # config, security(argon2/session), deps(角色守卫)
│   │   ├── db/                  # async session, base
│   │   ├── models/              # SQLAlchemy 模型
│   │   ├── schemas/             # Pydantic v2
│   │   ├── api/v1/endpoints/    # auth, users, courses, sections, enrollments, assignments, submissions, sse, admin
│   │   ├── services/            # enrollment_service(事务), notification, storage(minio)
│   │   └── batch/               # (stretch) 抽奖分配器
│   ├── alembic/
│   ├── tests/                   # 含 test_enroll_concurrency.py
│   ├── scripts/seed_data.py     # 种子数据（随 api 镜像发布，容器内执行）
│   └── pyproject.toml
├── frontend/
│   ├── app/                     # (student)/(teacher)/(admin) 路由组 + /login
│   ├── components/              # shadcn/ui 组件
│   └── lib/                     # api(generated), auth, sse
└── loadtest/locustfile.py
```
