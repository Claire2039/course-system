"""口令哈希、令牌/初始口令生成、口令策略。

argon2 哈希器与 ``scripts/seed_data.py`` 使用同一套默认参数，保证种子账号可被校验通过。
"""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from email_validator import EmailNotValidError, validate_email

# 与 scripts/seed_data.py 完全一致的哈希器（默认参数）。
_HASHER = PasswordHasher()

MIN_PASSWORD_LENGTH = 8
INITIAL_PASSWORD_ENTROPY_BYTES = 12  # token_urlsafe(12) ≈ 16 chars, ~95-bit
SESSION_TOKEN_ENTROPY_BYTES = 32  # token_urlsafe(32) ≈ 43 chars, 256-bit


def hash_password(plain: str) -> str:
    """argon2 哈希明文口令。"""
    return _HASHER.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    """校验口令：匹配返回 True，不匹配返回 False（损坏的哈希串向上抛 InvalidHash）。"""
    try:
        _HASHER.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    """opaque 会话令牌（256-bit，未签名；Redis 为权威源）。"""
    return secrets.token_urlsafe(SESSION_TOKEN_ENTROPY_BYTES)


def generate_initial_password() -> str:
    """导入用户的初始随机口令（仅返回一次，绝不落库）。"""
    return secrets.token_urlsafe(INITIAL_PASSWORD_ENTROPY_BYTES)


def validate_email_format(email: str) -> str:
    """仅做邮箱格式/结构校验（不做 DNS 可达性检查，避免依赖网络）；非法抛 ``ValueError``。"""
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return email


def validate_password_change(new_password: str, old_password: str) -> None:
    """改密策略校验；不满足抛 ``ValueError(code)``，由调用方转 400。

    code ∈ {"password_too_short", "same_as_old"}。
    """
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValueError("password_too_short")
    if new_password == old_password:
        raise ValueError("same_as_old")
