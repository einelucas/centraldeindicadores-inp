"""Divisão de registros em lotes. Porte literal de `src/lib/batching/index.ts`."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")

DEFAULT_IMPORT_BATCH_SIZE = 500


def chunk(items: list[T], size: int = DEFAULT_IMPORT_BATCH_SIZE) -> list[list[T]]:
    if size <= 0:
        raise ValueError("Tamanho de lote deve ser maior que zero")
    return [items[i : i + size] for i in range(0, len(items), size)]
