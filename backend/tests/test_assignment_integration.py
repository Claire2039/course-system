"""作业集成测试：需 TEST_DATABASE_URL；Redis→fakeredis，存储→InMemoryStorage。

覆盖：教师布置 → 学生提交（带文件）→ /me/assignments 可见 → 教师批改 → 学生见分 →
下载附件；重交；权限 403；过硬截止 409。
"""

from datetime import timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.main import app
from app.models import (
    Assignment,
    Course,
    Enrollment,
    Section,
    Semester,
    Student,
    Teacher,
    User,
)
from app.models.constants import EnrollmentStatus, SubmissionStatus, UserRole
from datetime import datetime

pytestmark = pytest.mark.integration

PWD = "StuPass#1"
NOW = datetime.now(timezone.utc)


async def _seed(db) -> tuple[int, str, str]:
    """返回 (section_id, teacher_email, student_email)。"""
    async with db() as s:
        sem = Semester(
            name="Fall",
            is_current=True,
            enroll_open_at=NOW - timedelta(days=10),
            enroll_close_at=NOW + timedelta(days=30),
            drop_deadline=NOW + timedelta(days=60),
            max_credits=30,
            max_courses=8,
        )
        s.add(sem)
        tu = User(
            email="tassign@seed.example.com",
            password_hash=hash_password("T#1"),
            role=UserRole.TEACHER,
            name="Prof",
            must_change_password=False,
            teacher=Teacher(teacher_no="TA1", department="CS", title="Lecturer"),
        )
        s.add(tu)
        su = User(
            email="sassign@seed.example.com",
            password_hash=hash_password(PWD),
            role=UserRole.STUDENT,
            name="Stu",
            must_change_password=False,
            student=Student(student_no="SAS1", grade=2024, major="CS"),
        )
        s.add(su)
        c = Course(code="AS101", title="Assignments", credits=3, department="CS")
        s.add(c)
        await s.flush()
        sec = Section(
            course_id=c.id,
            teacher_id=tu.id,
            semester_id=sem.id,
            capacity=50,
            seats_taken=1,
            room="R",
        )
        s.add(sec)
        await s.flush()
        s.add(
            Enrollment(
                student_id=su.id,
                section_id=sec.id,
                status=EnrollmentStatus.ENROLLED,
            )
        )
        await s.commit()
        return sec.id, "tassign@seed.example.com", "sassign@seed.example.com"


async def _login(ac: AsyncClient, email: str, pwd: str = "T#1") -> None:
    if email == "sassign@seed.example.com":
        pwd = PWD
    r = await ac.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text


async def test_create_submit_grade_flow(auth_db) -> None:
    sec_id, teacher, student = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 教师布置作业（截止在未来 → 可按时提交）
        await _login(ac, teacher)
        r = await ac.post(
            f"/api/v1/sections/{sec_id}/assignments",
            json={
                "title": "HW1",
                "description": "写一篇",
                "due_at": (NOW + timedelta(days=7)).isoformat(),
                "allow_late": True,
                "late_deadline": (NOW + timedelta(days=14)).isoformat(),
            },
        )
        assert r.status_code == 200, r.text
        aid = r.json()["id"]

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 学生提交（带文件 + 文字）
        await _login(ac, student)
        r = await ac.post(
            f"/api/v1/assignments/{aid}/submit",
            files={"file": ("hw.txt", b"hello world", "text/plain")},
            data={"text_comment": "第一次提交"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "SUBMITTED"
        assert r.json()["has_file"] is True
        sid = r.json()["id"]

        # /me/assignments 可见该作业与提交
        r = await ac.get("/api/v1/me/assignments")
        assert r.status_code == 200
        item = next(i for i in r.json() if i["assignment"]["id"] == aid)
        assert item["submission"]["status"] == "SUBMITTED"
        assert item["grade"] is None

        # 下载附件
        r = await ac.get(f"/api/v1/submissions/{sid}/file")
        assert r.status_code == 200
        assert r.content == b"hello world"

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 教师批改
        await _login(ac, teacher)
        r = await ac.post(
            f"/api/v1/submissions/{sid}/grade",
            json={"score": 88.5, "feedback": "不错"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["score"] == 88.5
        # 花名册
        r = await ac.get(
            f"/api/v1/sections/{sec_id}/submissions", params={"assignment_id": aid}
        )
        assert r.status_code == 200
        row = next(x for x in r.json() if x["student_no"] == "SAS1")
        assert row["grade"]["score"] == 88.5

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 学生见分
        await _login(ac, student)
        r = await ac.get("/api/v1/me/assignments")
        item = next(i for i in r.json() if i["assignment"]["id"] == aid)
        assert item["grade"]["score"] == 88.5


async def test_resubmit_updates_row(auth_db) -> None:
    sec_id, teacher, student = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, teacher)
        aid = (
            await ac.post(
                f"/api/v1/sections/{sec_id}/assignments",
                json={"title": "HW", "due_at": (NOW + timedelta(days=7)).isoformat()},
            )
        ).json()["id"]
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, student)
        r1 = await ac.post(
            f"/api/v1/assignments/{aid}/submit",
            files={"file": ("v1.txt", b"v1", "text/plain")},
        )
        r2 = await ac.post(
            f"/api/v1/assignments/{aid}/submit",
            files={"file": ("v2.txt", b"v2-new", "text/plain")},
        )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]  # 同一行（重交）
        # 下载得到最新内容
        r = await ac.get(f"/api/v1/submissions/{r2.json()['id']}/file")
        assert r.content == b"v2-new"


async def test_submit_deadline_passed_409(auth_db) -> None:
    sec_id, teacher, student = await _seed(auth_db)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, teacher)
        aid = (
            await ac.post(
                f"/api/v1/sections/{sec_id}/assignments",
                json={"title": "Old", "due_at": (NOW - timedelta(days=1)).isoformat()},
            )
        ).json()["id"]
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, student)
        r = await ac.post(f"/api/v1/assignments/{aid}/submit", data={"text_comment": "x"})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "deadline_passed"


async def test_permissions(auth_db) -> None:
    sec_id, teacher, _student = await _seed(auth_db)
    # 另一个未选课学生
    async with auth_db() as s:
        s.add(
            User(
                email="other@seed.example.com",
                password_hash=hash_password(PWD),
                role=UserRole.STUDENT,
                name="Other",
                must_change_password=False,
                student=Student(student_no="SOT1", grade=2024, major="CS"),
            )
        )
        await s.commit()
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await _login(ac, teacher)
        aid = (
            await ac.post(
                f"/api/v1/sections/{sec_id}/assignments",
                json={"title": "HW", "due_at": (NOW + timedelta(days=7)).isoformat()},
            )
        ).json()["id"]
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 未选课学生提交 → 403
        await _login(ac, "other@seed.example.com")
        r = await ac.post(f"/api/v1/assignments/{aid}/submit", data={"text_comment": "x"})
        assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
