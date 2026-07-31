"""core/security 纯单元测试（无需任何基础设施）。"""

import pytest

from app.core import security


def test_hash_and_verify_roundtrip() -> None:
    h = security.hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert security.verify_password(h, "s3cret-pass") is True


def test_verify_rejects_wrong_password() -> None:
    h = security.hash_password("s3cret-pass")
    assert security.verify_password(h, "wrong") is False


def test_session_tokens_are_long_and_unique() -> None:
    tokens = {security.generate_session_token() for _ in range(1000)}
    assert len(tokens) == 1000  # 无碰撞
    assert all(len(t) >= 30 for t in tokens)


def test_initial_passwords_meet_policy_and_are_unique() -> None:
    pws = {security.generate_initial_password() for _ in range(500)}
    assert len(pws) == 500
    for p in pws:
        assert len(p) >= security.MIN_PASSWORD_LENGTH


def test_policy_rejects_too_short() -> None:
    with pytest.raises(ValueError) as ei:
        security.validate_password_change("short", "oldpass123")
    assert "password_too_short" in str(ei.value)


def test_policy_rejects_same_as_old() -> None:
    with pytest.raises(ValueError) as ei:
        security.validate_password_change("samepass1", "samepass1")
    assert "same_as_old" in str(ei.value)


def test_policy_accepts_strong_change() -> None:
    # 不抛即通过
    security.validate_password_change("a-strong-new-password", "oldpass123")
