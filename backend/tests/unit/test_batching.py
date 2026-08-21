"""Porte de comportamento de `src/lib/batching/index.ts`."""

from __future__ import annotations

import pytest

from app.shared.batching import DEFAULT_IMPORT_BATCH_SIZE, chunk


def test_chunk_splits_into_equal_groups() -> None:
    assert chunk([1, 2, 3, 4], size=2) == [[1, 2], [3, 4]]


def test_chunk_last_group_may_be_smaller() -> None:
    assert chunk([1, 2, 3, 4, 5], size=2) == [[1, 2], [3, 4], [5]]


def test_chunk_empty_list_returns_empty() -> None:
    assert chunk([], size=10) == []


def test_chunk_default_size_is_500() -> None:
    assert DEFAULT_IMPORT_BATCH_SIZE == 500
    items = list(range(1200))
    result = chunk(items)
    assert len(result) == 3
    assert len(result[0]) == 500
    assert len(result[-1]) == 200


def test_chunk_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError, match="maior que zero"):
        chunk([1, 2, 3], size=0)
