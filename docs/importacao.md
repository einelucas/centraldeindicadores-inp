# Importação de dados

RDO, IDP, RNC e 5S recebem dados por importação de arquivo (Excel, CSV ou
PDF, dependendo do módulo). Taxa de Acidentes é a exceção: seus lançamentos
são cadastrados diretamente por formulário na Administração, sem upload de
arquivo nem processo de importação.

## Princípios

- **nunca apaga o período.** A ausência de uma linha em uma nova planilha
  não remove o que já existe para aquele mês/unidade.
- **parsing no navegador.** O arquivo é lido e normalizado no cliente
  (frontend); apenas o JSON já estruturado é enviado à API. O arquivo
  original nunca é persistido no servidor.
- **chaves geradas no servidor.** Mesmo que o cliente já tenha normalizado
  os dados, a API é quem gera a business key e o content hash de cada
  registro — essa é a fonte de verdade.
- **idempotência por lote.** Cada lote é identificado por
  `(importJobId, batchNumber)`; reenviar o mesmo lote não duplica efeitos.

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
status) **sem duplicar a linha** e sem apagar o histórico do período.

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

## Fluxo de uma importação

1. **Iniciar** — `POST /api/v1/importacoes/iniciar` cria um job de
   importação para um módulo e devolve `importJobId`.
2. **Enviar lotes** — o frontend lê o arquivo, normaliza, quebra em lotes
   (tamanho configurável, `NUXT_PUBLIC_IMPORT_BATCH_SIZE`, padrão 500) e
   envia cada um para `POST /api/v1/importacoes/{id}/lotes` com o número
   do lote.
3. **Processar** — para cada registro do lote, o motor incremental decide
   inserir/ignorar/atualizar. Erros de linha são registrados sem abortar o
   restante do lote.
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
  erros de linha.
- Para excluir dados administrativos de um módulo, primeiro um `GET
  /api/v1/<modulo>/registros` retorna a contagem de registros afetados
  pelo período escolhido (ou pela base inteira), e só depois um `DELETE`
  no mesmo caminho executa a exclusão. Isso nunca apaga a publicação
  vigente — apenas os dados administrativos de origem.
