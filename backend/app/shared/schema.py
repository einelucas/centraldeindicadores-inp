"""Base Pydantic compartilhada — payloads em `camelCase` (mesmo formato do
Next.js atual), aceitando também nomes em `snake_case` na entrada para
facilitar testes/clientes Python, e sempre serializando em `camelCase`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
