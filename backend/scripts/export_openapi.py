"""导出 OpenAPI 规范到 frontend/openapi.json，供 openapi-typescript 生成前端类型。

无需启动服务——直接从 FastAPI app 取 schema。在 backend/ 下执行：

    python -m scripts.export_openapi
"""

from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    # scripts/export_openapi.py → parents[2] = repo root
    return Path(__file__).resolve().parents[2]


def main() -> None:
    from app.main import app

    spec = app.openapi()
    out = _repo_root() / "frontend" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
