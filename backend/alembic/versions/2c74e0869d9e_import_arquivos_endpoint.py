"""import_arquivos_endpoint

Suporte de schema para o endpoint novo `POST /importacoes/{modulo}/arquivos`
(upload multipart, parsing no servidor):

- `ImportJob.idempotencyKey` — reenvio com a mesma chave devolve o job já
  concluído em vez de reprocessar. Nullable e único em conjunto com
  `module` (jobs do fluxo antigo, sem chave, ficam com `NULL` — Postgres não
  considera múltiplos `NULL` como colisão de unicidade).
- Tabela `ImportFile` — granularidade por arquivo quando vários arquivos são
  enviados no mesmo POST (o fluxo antigo, de lote único, não precisa: já
  usa `ImportJob.fileName`).
- `ImportError.fileName` — permite reportar erro por arquivo+linha no fluxo
  novo (o fluxo antigo só tinha `batchNumber`).

Revision ID: 2c74e0869d9e
Revises: 7c7156aae822
Create Date: 2026-09-09 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '2c74e0869d9e'
down_revision: Union[str, None] = '7c7156aae822'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ImportJob', sa.Column('idempotencyKey', sa.String(), nullable=True))
    op.create_index(
        'ImportJob_module_idempotencyKey_key',
        'ImportJob',
        ['module', 'idempotencyKey'],
        unique=True,
    )

    op.add_column('ImportError', sa.Column('fileName', sa.String(), nullable=True))

    op.create_table(
        'ImportFile',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('importJobId', sa.String(), nullable=False),
        sa.Column('fileName', sa.String(), nullable=False),
        sa.Column('found', sa.Integer(), nullable=False),
        sa.Column('accepted', sa.Integer(), nullable=False),
        sa.Column('rejected', sa.Integer(), nullable=False),
        sa.Column('processedAt', postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.ForeignKeyConstraint(
            ['importJobId'], ['ImportJob.id'], ondelete='CASCADE', onupdate='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ImportFile_importJobId_idx', 'ImportFile', ['importJobId'], unique=False)


def downgrade() -> None:
    op.drop_index('ImportFile_importJobId_idx', table_name='ImportFile')
    op.drop_table('ImportFile')

    op.drop_column('ImportError', 'fileName')

    op.drop_index('ImportJob_module_idempotencyKey_key', table_name='ImportJob')
    op.drop_column('ImportJob', 'idempotencyKey')
