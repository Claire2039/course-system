from fastapi.testclient import TestClient

from app.main import app


async def _ok_db() -> None:
    return None


async def _ok_redis(app) -> None:  # noqa: ANN001
    return None


async def _raise(*args, **kwargs) -> None:
    raise OSError("down")


def test_health_ok() -> None:
    """存活探针：进程在跑即 200，不依赖任何外部服务。"""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "course-api"


def test_readiness_503_when_db_down(monkeypatch) -> None:
    """就绪探针：DB 不可达时 503（Redis 视为正常，隔离 DB 这一项）。"""
    monkeypatch.setattr("app.main._ping_db", _raise)
    monkeypatch.setattr("app.main._ping_redis", _ok_redis)
    client = TestClient(app)
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["detail"]["status"] == "unhealthy"


def test_readiness_503_when_redis_down(monkeypatch) -> None:
    """就绪探针：Redis 不可达时 503（DB 视为正常，隔离 Redis 这一项）。"""
    monkeypatch.setattr("app.main._ping_db", _ok_db)
    monkeypatch.setattr("app.main._ping_redis", _raise)
    client = TestClient(app)
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["detail"]["status"] == "unhealthy"
