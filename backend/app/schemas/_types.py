"""共享 Pydantic 类型。

``Email``：仅格式校验的邮箱类型（不做 DNS 可达性检查），供各 schema 复用。
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

from app.core.security import validate_email_format

Email = Annotated[str, AfterValidator(validate_email_format)]
