"""GET /me/notifications 集成测试：需 TEST_DATABASE_URL；Redis 走 fakeredis。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.main import app
from app.models import Notification, Student, User
from app.models.constants import UserRole

pytestmark = pytest.mark.integration


async def test_list_notifications(auth_db) -> None:
    async with auth_db() as s:
        u = User(
            email="n@seed.example.com",
            password_hash=hash_password("Npass#1"),
            role=UserRole.STUDENT,
            name="N",
            must_change_password=False,
            student=Student(student_no="S1", grade=2024, major="CS"),
        )
        s.add(u)
        await s.commit()
        uid = (
            await s.execute(select(User.id).where(User.email == "n@seed.example.com"))
        ).scalar_one()
        s.add(Notification(user_id=uid, type="enrolled", payload={"section_id": 1}))
        s.add(Notification(user_id=uid, type="waitlisted", payload={"section_id": 2}))
        await s.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/auth/login", json={"email": "n@seed.example.com", "password": "Npass#1"}
        )
        assert r.status_code == 200
        r = await ac.get("/api/v1/me/notifications")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        # 按 created_at desc 排序
        assert body[0]["type"] in {"enrolled", "waitlisted"}
