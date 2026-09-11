"""remove_taxa_acidentes

Remove as duas tabelas exclusivas do módulo Taxa de Acidentes, descontinuado
no alinhamento 2026-alinhamento-v2 (ver docs/scorecard.md). Só as duas
tabelas do módulo — nada de `CASCADE`, nada de outras estruturas. Dados em
tabelas compartilhadas (`IndicatorPublication`, `IndicatorResult`,
`IndicatorJustification`, `AppSetting`, auditoria, snapshots do Scorecard)
são responsabilidade da rotina controlada
`scripts/remove_taxa_acidentes_data.py --apply`, não desta migration — ela
já chama `alembic upgrade head` ao final, então normalmente é o único lugar
de onde esta migration deveria ser aplicada em um banco com dados reais.

Revision ID: 7c7156aae822
Revises: 0c528c3c79e5
Create Date: 2026-09-04 10:11:07.396899
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '7c7156aae822'
down_revision: Union[str, None] = '0c528c3c79e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('AccidentUnitRecord_year_month_unitKey_key', table_name='AccidentUnitRecord')
    op.drop_index('AccidentUnitRecord_year_month_idx', table_name='AccidentUnitRecord')
    op.drop_index('AccidentUnitRecord_unit_idx', table_name='AccidentUnitRecord')
    op.drop_table('AccidentUnitRecord')
    op.drop_index('AccidentMonthlyRecord_year_month_key', table_name='AccidentMonthlyRecord')
    op.drop_index('AccidentMonthlyRecord_year_month_idx', table_name='AccidentMonthlyRecord')
    op.drop_table('AccidentMonthlyRecord')


def downgrade() -> None:
    op.create_table(
        'AccidentMonthlyRecord',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('caf', sa.Integer(), nullable=False),
        sa.Column('createdAt', postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column('updatedAt', postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'AccidentMonthlyRecord_year_month_idx', 'AccidentMonthlyRecord', ['year', 'month'], unique=False
    )
    op.create_index(
        'AccidentMonthlyRecord_year_month_key', 'AccidentMonthlyRecord', ['year', 'month'], unique=True
    )
    op.create_table(
        'AccidentUnitRecord',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('unitKey', sa.String(), nullable=False),
        sa.Column('saf', sa.Integer(), nullable=False),
        sa.Column('caf', sa.Integer(), nullable=False),
        sa.Column('createdAt', postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.Column('updatedAt', postgresql.TIMESTAMP(precision=3), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('AccidentUnitRecord_unit_idx', 'AccidentUnitRecord', ['unit'], unique=False)
    op.create_index(
        'AccidentUnitRecord_year_month_idx', 'AccidentUnitRecord', ['year', 'month'], unique=False
    )
    op.create_index(
        'AccidentUnitRecord_year_month_unitKey_key',
        'AccidentUnitRecord',
        ['year', 'month', 'unitKey'],
        unique=True,
    )
