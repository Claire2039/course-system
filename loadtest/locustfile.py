"""locust 压测脚本：模拟"选课窗口一开、大量学生涌入抢课"。

演示 FCFS 条件 UPDATE 在真实并发负载下**零超卖**：对某个 capacity=N 的教学班，
无论多少并发，最终恰好 N 个 ENROLLED、其余 WAITLISTED。

前置：已执行 ``python -m scripts.seed_data``（2000 学生，初始口令 InitPass#2026，首登强制改密）。
本脚本会自动把所用学生口令改为固定值 LoadTest#1（幂等：已改则直接用新口令登录）。

运行（在能访问 API 的机器上，例如本机或服务器）：
    pip install locust
    # Web UI 模式：
    locust -f loadtest/locustfile.py --host http://<API地址>
    # 无头模式（建议做零超卖演示）：
    locust -f loadtest/locustfile.py --host http://<API地址> --headless -u 500 -r 50 -t 1m

环境变量：
    LOADTEST_SECTION_ID  要抢的教学班 id（默认 1；可挑一个 capacity 较小的班看效果）
    LOADTEST_OFFSET      学生编号起始（多 worker 分布时每个 worker 设不同值，默认 1）
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task

INITIAL_PWD = "InitPass#2026"
PWD = "LoadTest#1"
EMAIL_TMPL = "student{:04d}@seed.example.com"
SECTION_ID = int(os.environ.get("LOADTEST_SECTION_ID", "1"))
OFFSET = int(os.environ.get("LOADTEST_OFFSET", "1"))

# 进程内自增计数器，保证单进程内每个虚拟用户用一个不重复的学生。
_counter = 0


def _next_email() -> str:
    global _counter
    _counter += 1
    return EMAIL_TMPL.format(OFFSET + _counter - 1)


class StudentUser(HttpUser):
    """一个虚拟用户 = 一个学生：登录（必要时改密）→ 浏览/抢课。"""

    wait_time = between(0.1, 0.5)
    abstract = False

    def on_start(self) -> None:
        self.email = _next_email()
        # 幂等改密：先用新口令登录；失败说明还没改，用初始口令登录后改密。
        if not self._login(PWD):
            self._login(INITIAL_PWD)
            with self.client.post(
                "/api/v1/auth/change-password",
                json={"old_password": INITIAL_PWD, "new_password": PWD},
                catch_response=True,
            ) as r:
                r.success()  # 设置阶段，不计为业务失败

    def _login(self, pwd: str) -> bool:
        with self.client.post(
            "/api/v1/auth/login",
            json={"email": self.email, "password": pwd},
            catch_response=True,
        ) as r:
            ok = r.status_code == 200
            r.success()  # on_start 容错，不污染统计
            return ok

    @task(3)
    def browse_sections(self) -> None:
        with self.client.get("/api/v1/sections", catch_response=True) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"browse {r.status_code}")

    @task(1)
    def enroll(self) -> None:
        with self.client.post(
            f"/api/v1/sections/{SECTION_ID}/enroll", catch_response=True
        ) as r:
            # 200(选上/候补) 或 409(已选/时间冲突/满) 都是预期内的业务结果
            if r.status_code in (200, 409):
                r.success()
            else:
                r.failure(f"enroll {r.status_code}: {r.text[:120]}")
