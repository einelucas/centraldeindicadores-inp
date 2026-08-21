"""Endpoints de saúde — sem autenticação, usados por orquestradores/probes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.database import check_database_ready

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(response: Response) -> dict[str, str]:
    try:
        ok = await check_database_ready()
    except Exception:
        ok = False
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
