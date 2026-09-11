# Importação de dados

RDO, IDP, RNC e 5S recebem dados por importação de arquivo (Excel, CSV ou
PDF, dependendo do módulo).

**Estado da migração (ver plano de fases):** RDO e RNC já usam o fluxo novo,
descrito abaixo, com parsing/validação/normalização/dedup/persistência
inteiramente no FastAPI. 5S e IDP ainda usam o fluxo antigo (parsing no
navegador + 3 chamadas), documentado na seção "Fluxo antigo" — serão
migrados nas próximas fases, reaproveitando a mesma infraestrutura
(`app/modules/imports/parsers/`, `bulk_upsert.py`) já construída para RDO.

## Princípios

- **nunca apaga o período.** A ausência de uma linha em uma nova planilha
  não remove o que já existe para aquele mês/unidade.
- **parsing no servidor (RDO e RNC) / no navegador (5S e IDP — por enquanto).**
  Para os módulos já migrados, o arquivo original é enviado por
  `multipart/form-data` e lido/normalizado inteiramente no FastAPI — o
  navegador nunca interpreta Excel/CSV/PDF. Para os módulos ainda no fluxo
  antigo, o arquivo é lido no cliente e só o JSON já estruturado é enviado.
- **chaves geradas no servidor.** Em ambos os fluxos, é a API quem gera a
  business key e o content hash de cada registro — essa é a fonte de
  verdade, nunca o cliente.
- **idempotência.** No fluxo novo, todo o upload de um envio é identificado
  por um cabeçalho `Idempotency-Key`; reenviar os mesmos arquivos com a
  mesma chave devolve o resultado já processado em vez de reprocessar. No
  fluxo antigo, cada lote é identificado por `(importJobId, batchNumber)`.

## Business key e content hash

Toda importação incremental depende de duas chaves geradas no servidor
para decidir entre inserir, ignorar ou atualizar um registro
(`backend/app/shared/hashing.py`):

- **business key** — identidade lógica do registro: "isto representa a
  mesma coisa do mundo real que já está no banco?". Composta pelos campos
  **estáveis** (que não mudam entre reimportações) e indexada como única
  no banco.
- **content hash** — hash apenas dos campos **mutáveis** (por exemplo, o
  status de um relatório). Se a business key já existe e o content hash é
  igual, o registro é idêntico → ignorado. Se o hash mudou, só aquele
  registro é atualizado.

Separar identidade de conteúdo permite corrigir um campo mutável (como
status) **sem duplicar a linha** e sem apagar o histórico do período. Essa
lógica é idêntica nos dois fluxos — o que muda entre eles é só onde o
arquivo é lido, nunca como a chave/hash são calculados.

### Exemplo — RDO

Um mesmo relatório pode gerar várias linhas (uma por grupo/disciplina), e o
`relatorioId` sozinho não identifica uma linha:

```text
businessKey(RDO) = SHA-256("RDO" | relatorioId | dataISO | empresaNome | grupo | disciplina)
contentHash(RDO) = SHA-256({ statusDescricao, responsavel, observacao })
```

Implementação em `backend/app/modules/rdo/keys.py`; helpers genéricos em
`backend/app/shared/hashing.py`.

| Situação na reimportação | Resultado |
|---|---|
| Linha nova (business key inédita) | inserida |
| Linha idêntica (mesma chave, mesmo hash) | ignorada |
| Mesmo relatório, status mudou (mesma chave) | atualizada |
| Linha ausente na nova planilha | mantida como estava |

## Fluxo novo — upload direto (RDO e RNC)

```http
POST /api/v1/importacoes/{modulo}/arquivos
Content-Type: multipart/form-data
Idempotency-Key: <uuid gerado pelo cliente por tentativa de envio>

files: relatorio1.xlsx
files: relatorio2.csv
```

Formatos aceitos: `.xlsx`, `.xls`, `.xlsm`, `.xlsb`, `.xltx`, `.xlt`, `.csv`
(Excel/CSV) e `.pdf` (só IDP, quando migrado). A assinatura real do arquivo
é validada (magic bytes), não só a extensão — um arquivo corrompido ou
disfarçado é rejeitado com uma mensagem clara, nunca aceito silenciosamente.

O FastAPI faz todo o ciclo numa única chamada, dentro de uma transação
atômica (falha em qualquer etapa desfaz tudo daquele envio):

1. Cria o `ImportJob` (ou devolve o já existente, se a `Idempotency-Key`
   já tiver sido usada com sucesso para este módulo).
2. Lê cada arquivo em uma thread separada (`asyncio.to_thread`), com no
   máximo `IMPORT_FILE_CONCURRENCY` (padrão 3) em paralelo —
   `app/modules/imports/parsers/{excel,csv_parser,rdo,rnc}.py`.
3. Deduplica linhas 100% idênticas entre os arquivos do mesmo envio.
4. Normaliza cada linha para o shape de entrada do módulo e chama
   `to_incremental_records()` do módulo — a mesma função usada pelo fluxo
   antigo, sem alteração: gera business key/content hash.
5. **Bulk upsert** (`app/modules/imports/bulk_upsert.py`), substituindo o
   loop linha-a-linha do fluxo antigo: por lote interno de ~750 registros,
   uma única `SELECT businessKey, contentHash WHERE businessKey = ANY(...)`
   seguida de um único `INSERT ... ON CONFLICT (businessKey) DO UPDATE`
   cobrindo todos os inserts+updates do lote (registros ignorados nem
   entram no `INSERT`).
6. Recalcula o indicador do módulo **uma única vez**, ao final (não por
   arquivo nem por lote).
7. Grava o histórico por arquivo (`ImportFile`) e por erro
   (`ImportError.fileName` + `rowNumber` + `message`).

Resposta consolidada:

```json
{
  "importJobId": "uuid",
  "status": "COMPLETED",
  "totals": { "found": 1800, "inserted": 1700, "updated": 40, "ignored": 55, "rejected": 5 },
  "files": [
    {
      "fileName": "relatorio1.xlsx",
      "found": 300,
      "accepted": 299,
      "rejected": 1,
      "errors": [{ "row": 18, "field": "data", "message": "Data inválida." }]
    }
  ],
  "durationMs": 2800
}
```

Limites (configuráveis via `.env`, ver `backend/app/core/config.py`):
`MAX_IMPORT_FILES` (padrão 10), `MAX_IMPORT_FILE_SIZE_BYTES` (20 MB),
`MAX_IMPORT_TOTAL_SIZE_BYTES` (100 MB), `MAX_IMPORT_ROWS_PER_FILE`
(200.000), `IMPORT_FILE_CONCURRENCY` (3).

O composable do Nuxt (`frontend/composables/useFileUpload.ts`) só monta um
`FormData` com os arquivos originais e envia — nenhum parsing acontece no
navegador para RDO ou RNC.

## Fluxo antigo — 3 chamadas (5S e IDP)

1. **Iniciar** — `POST /api/v1/importacoes/iniciar` cria um job de
   importação para um módulo e devolve `importJobId`.
2. **Enviar lotes** — o frontend lê o arquivo, normaliza, quebra em lotes
   (tamanho configurável, `NUXT_PUBLIC_IMPORT_BATCH_SIZE`, padrão 500) e
   envia cada um para `POST /api/v1/importacoes/{id}/lotes` com o número
   do lote.
3. **Processar** — para cada registro do lote, o motor incremental
   (`app/shared/incremental_upsert.py::process_incremental_batch`) decide
   inserir/ignorar/atualizar **um registro por vez** (não em lote SQL).
   Erros de linha são registrados sem abortar o restante do lote.
4. **Finalizar** — `POST /api/v1/importacoes/{id}/finalizar` marca o job
   como concluído e recalcula os indicadores do módulo.

Cada lote devolve um resumo:

| Campo | Significado |
|---|---|
| `inserted` | registros novos |
| `updated` | existiam e tiveram algum campo mutável alterado |
| `ignored` | idênticos ao que já existia |
| `rejected` | falharam na validação |
| `errors[]` | detalhe por linha/business key |

## Consultando e limpando o histórico

- `GET /api/v1/importacoes` lista os jobs; `GET /api/v1/importacoes/{id}`
  traz o detalhe de um job; `GET /api/v1/importacoes/{id}/erros` lista os
  erros de linha. Válido para os dois fluxos.
- Para excluir dados administrativos de um módulo, primeiro um `GET
  /api/v1/<modulo>/registros` retorna a contagem de registros afetados
  pelo período escolhido (ou pela base inteira), e só depois um `DELETE`
  no mesmo caminho executa a exclusão. Isso nunca apaga a publicação
  vigente — apenas os dados administrativos de origem.
