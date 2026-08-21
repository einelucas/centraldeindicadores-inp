"""Tratamento uniforme de erros — mensagens seguras em português, sem stack trace."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.permissions import ForbiddenError

logger = logging.getLogger("app.errors")


class UnauthorizedError(Exception):
    """Ausência de autenticação válida (401)."""

    def __init__(self, message: str = "Não autenticado") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(Exception):
    """Entidade não encontrada (404)."""

    def __init__(self, message: str = "Recurso não encontrado") -> None:
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    """Conflito de estado — ex.: concorrência de versão (409)."""

    def __init__(self, message: str = "Conflito ao processar a requisição") -> None:
        self.message = message
        super().__init__(message)


class DomainError(Exception):
    """Erro de regra de negócio — vira 422 com mensagem segura ao usuário."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnauthorizedError)
    async def _unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": exc.message})

    @app.exception_handler(ForbiddenError)
    async def _forbidden(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": str(exc)})

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": exc.message})

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": exc.message})

    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"error": exc.message}
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Dados inválidos", "issues": exc.errors()},
        )

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Dados inválidos", "issues": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", None)
        logger.exception(
            "Erro não tratado", extra={"correlation_id": correlation_id, "path": request.url.path}
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Erro interno ao processar a requisição"},
        )
