"""通知 pub/sub + schema 单元测试（fakeredis，无需真 Redis）。"""

from datetime import datetime, timezone

import fakeredis.aioredis
import pytest

from app.schemas.notification import NotificationOut
from app.services.notification import publish_event


async def test_publish_event_received_by_subscriber() -> None:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ps = client.pubsub()
    await ps.subscribe("notify:ch:42")

    await publish_event(client, 42, "enrolled", {"section_id": 1})

    received = None
    for _ in range(20):
        msg = await ps.get_message(timeout=1.0)
        if msg and msg.get("type") == "message":
            received = msg["data"]
            break
    await ps.unsubscribe("notify:ch:42")
    await ps.aclose()

    assert received is not None
    assert "enrolled" in received
    assert "section_id" in received


def test_notification_out_shape() -> None:
    n = NotificationOut(
        id=1,
        type="waitlisted",
        payload={"section_id": 7, "position": 3},
        read=False,
        created_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    dumped = n.model_dump(mode="json")
    assert dumped["type"] == "waitlisted"
    assert dumped["payload"]["position"] == 3
    assert dumped["read"] is False


@pytest.mark.parametrize("event_type", ["enrolled", "waitlisted", "promoted", "dropped"])
async def test_publish_various_event_types(event_type: str) -> None:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await publish_event(client, 1, event_type, {"section_id": 1})
    # 不抛即通过（发布 best-effort）
