# Banco de dados

A Central de Indicadores usa PostgreSQL como banco principal. O backend acessa o banco por SQLAlchemy 2 assíncrono (`asyncpg`) e o schema é versionado com Alembic.

O frontend nunca acessa o banco diretamente.

## Modelos principais

- `User` — usuário local, perfil, status e vínculo com a identidade Keycloak;
- `ImportJob`, `ImportBatch`, `ImportFile`, `ImportError` — rastreio do processamento de arquivos e lotes;
- `IndicatorResult` — resultados administrativos consolidados;
- `IndicatorPublication` — publicações versionadas exibidas pelos painéis;
- `IndicatorJustification` — justificativas dos módulos suportados;
- `RdoRecord` — registros do RDO;
- `IdpRsoRecord` — registros de RSO usados pelo IDP;
- `RncRecord` — registros de não conformidades;
- `FiveSRecord` — registros do domínio 5S;
- `ScorecardSnapshot` — snapshots mensais do Scorecard;
- `AppSetting` — metas e parâmetros de aplicação;
- `AuditLog` — trilha de auditoria.

Alguns modelos auxiliares podem existir no schema sem participar do fluxo principal de autenticação ou cálculo. O uso efetivo de cada modelo deve ser verificado nos repositórios e serviços do backend.

## Configurações (`AppSetting`)

As configurações de negócio persistidas evitam hardcode de parâmetros que precisam ser alterados administrativamente.

Exemplos de chaves atuais:

| Chave | Valor padrão |
|---|---:|
| `rdo.target` | 0,80 |
| `idp.target` | 0,90 |
| `rnc.maxPrazoDias` | 15 |
| `fiveS.target` | 0,90 |
| `fiveS.excludedUnits` | SP, CSC |
| `scorecard.panelPeriod` | ciclo selecionado para o Painel Geral |

A tela de Configurações usa a API para ler e atualizar os valores permitidos.

## Publicações

`IndicatorPublication` mantém snapshots versionados dos resultados publicados pelos módulos.

A publicação é separada dos registros administrativos de origem. Isso permite editar/importar dados sem alterar imediatamente o painel de leitura.

O backend controla qual publicação está ativa para cada módulo e ciclo.

## Scorecard

`ScorecardSnapshot` armazena snapshots mensais da consolidação do Scorecard. Esses snapshots são respaldo histórico e não substituem os registros ou publicações dos módulos de origem.

Pesos e regras de participação dos indicadores não devem ser duplicados no banco como constantes arbitrárias; a fonte de verdade do Scorecard está no módulo `backend/app/modules/scorecard/`.

## Importações

O histórico de importação registra o processamento e seus resultados. Dependendo do fluxo utilizado pelo módulo, podem existir informações de job, lote, arquivo e erros de linha.

Business key e content hash dos registros são usados para persistência incremental e deduplicação.

## Alembic

Comandos principais, executados a partir de `backend/`:

```bash
alembic upgrade head
alembic revision --autogenerate -m "descricao"
alembic stamp head
```

### Segurança

O ambiente possui salvaguardas para evitar execução acidental de migrations ou testes destrutivos contra bancos inadequados.

Antes de aplicar migrations, confira:

- `APP_ENV`;
- `DATABASE_URL`;
- banco/host de destino;
- `ALLOW_TEST_DB_MIGRATIONS` quando exigido pelo ambiente.

A suíte de integração deve usar um PostgreSQL dedicado a testes.

## Scripts de apoio

```bash
python scripts/check_schema_drift.py
python scripts/seed.py
python scripts/export_openapi.py
```

- `check_schema_drift.py` compara os modelos SQLAlchemy com o schema acessível;
- `seed.py` aplica dados/configurações iniciais de forma idempotente;
- `export_openapi.py` exporta o contrato OpenAPI.

## Fonte de verdade

Modelos SQLAlchemy: `backend/app/models/`  
Migrations: `backend/alembic/`  
Configuração do banco: `backend/app/core/database.py`  
Configuração da aplicação: `backend/app/core/config.py`
