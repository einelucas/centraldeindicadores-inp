"""Paginação padrão com limites máximos."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import get_settings


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1)

    @classmethod
    def bounded(cls, page: int = 1, page_size: int | None = None) -> PageParams:
        settings = get_settings()
        size = page_size if page_size is not None else settings.default_page_size
        size = max(1, min(size, settings.max_page_size))
        return cls(page=max(1, page), page_size=size)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: list, total: int, params: PageParams) -> Page:
        total_pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            total_pages=max(total_pages, 1 if total else 0),
        )
