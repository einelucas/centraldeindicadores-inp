"""Ponto de entrada FastAPI — Central de Indicadores."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, install_correlation_id_middleware

settings = get_settings()
configure_logging()

app = FastAPI(
    title="Central de Indicadores — API",
    description=(
        "Backend FastAPI da Central de Indicadores (INPASA): autenticação, "
        "permissões, cálculo dos indicadores e persistência. Consulte "
        "docs/api.md para a lista completa de rotas por área."
    ),
    version="0.1.0",
    contact={"name": "Planejamento INPASA"},
)

install_correlation_id_middleware(app)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
