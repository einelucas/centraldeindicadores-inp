"""Exporta o schema OpenAPI completo para `backend/openapi.json`.

Uso:
    python scripts/export_openapi.py [caminho-de-saida]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "openapi.json"
    schema = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAPI exportado para {output_path} ({len(schema.get('paths', {}))} rotas).")


if __name__ == "__main__":
    main()
