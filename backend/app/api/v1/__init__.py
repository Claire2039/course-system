"""v1 API 路由聚合。在 main.py 中以 prefix="/api/v1" 挂载。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, assignments, auth, catalog, enrollments, events, me, teacher

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(enrollments.router, tags=["enrollment"])
api_router.include_router(events.router, tags=["realtime"])
api_router.include_router(me.router, tags=["me"])
api_router.include_router(assignments.router, tags=["assignment"])
api_router.include_router(teacher.router, tags=["teacher"])
