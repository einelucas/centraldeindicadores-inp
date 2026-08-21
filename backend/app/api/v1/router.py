"""Agregador de todos os routers de módulo sob o prefixo /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, health
from app.modules.audit.router import router as audit_router
from app.modules.cinco_s.router import router as cinco_s_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.idp.router import router as idp_router
from app.modules.imports.router import router as imports_router
from app.modules.indicators.router import router as indicators_router
from app.modules.justifications.router import router as justifications_router
from app.modules.rdo.router import router as rdo_router
from app.modules.rnc.router import router as rnc_router
from app.modules.scorecard.router import router as scorecard_router
from app.modules.settings.router import router as settings_router
from app.modules.taxa_acidentes.router import router as taxa_acidentes_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(imports_router)
api_router.include_router(rdo_router)
api_router.include_router(idp_router)
api_router.include_router(rnc_router)
api_router.include_router(cinco_s_router)
api_router.include_router(taxa_acidentes_router)
api_router.include_router(users_router)
api_router.include_router(settings_router)
api_router.include_router(audit_router)
api_router.include_router(indicators_router)
api_router.include_router(justifications_router)
api_router.include_router(scorecard_router)
api_router.include_router(dashboard_router)

# Os módulos de negócio se registram aqui à medida que são implementados
# (cada um chama `api_router.include_router(...)` a partir do seu próprio
# `router.py`, mantendo este arquivo como o único ponto de composição).
