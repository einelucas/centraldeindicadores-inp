"""Logs estruturados em JSON, com correlation id por requisição."""

from __future__ import annotations

import logging
import sys
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

CORRELATION_ID_HEADER = "X-Request-ID"


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class CorrelationIdMiddleware:
    """Middleware ASGI puro (não `BaseHTTPMiddleware`) — evita a indireção por
    task group que quebra a continuidade do greenlet usado pelo SQLAlchemy
    assíncrono (bug conhecido de `BaseHTTPMiddleware` + drivers assíncronos)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        correlation_id = headers.get(CORRELATION_ID_HEADER.lower().encode(), b"").decode() or str(
            uuid.uuid4()
        )
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id, path=scope.get("path"), method=scope.get("method")
        )

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].append(
                    (CORRELATION_ID_HEADER.encode(), correlation_id.encode())
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)


def install_correlation_id_middleware(app: FastAPI) -> None:
    app.add_middleware(CorrelationIdMiddleware)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
