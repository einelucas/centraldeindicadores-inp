"""Testes do utilitário de paginação genérico (`app/shared/pagination.py`),
usado por rotas de listagem que precisam de limites máximos configuráveis."""

from __future__ import annotations

from app.shared.pagination import Page, PageParams


def test_bounded_uses_defaults_when_page_size_not_given() -> None:
    params = PageParams.bounded()
    assert params.page == 1
    assert params.page_size == 50  # DEFAULT_PAGE_SIZE


def test_bounded_clamps_page_size_to_max() -> None:
    params = PageParams.bounded(page_size=10_000)
    assert params.page_size == 200  # MAX_PAGE_SIZE


def test_bounded_clamps_page_size_to_minimum_one() -> None:
    params = PageParams.bounded(page_size=0)
    assert params.page_size == 1


def test_bounded_clamps_page_to_minimum_one() -> None:
    params = PageParams.bounded(page=-5)
    assert params.page == 1


def test_offset_calculation() -> None:
    params = PageParams(page=3, page_size=20)
    assert params.offset == 40


def test_page_create_computes_total_pages() -> None:
    params = PageParams(page=1, page_size=10)
    page = Page.create(items=list(range(10)), total=25, params=params)
    assert page.total_pages == 3
    assert page.total == 25
    assert page.page == 1
    assert page.page_size == 10


def test_page_create_with_zero_total_has_zero_total_pages() -> None:
    params = PageParams(page=1, page_size=10)
    page = Page.create(items=[], total=0, params=params)
    assert page.total_pages == 0
