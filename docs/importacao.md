# Importação de dados

A Central de Indicadores possui uma infraestrutura comum para importar dados, validar registros, evitar duplicidades e recalcular os módulos.

Os detalhes variam conforme o formato de origem de cada indicador, mas a fonte de verdade para identidade e alteração de registros está sempre no backend.

## Princípios

- uma nova importação não apaga automaticamente registros que não aparecem no arquivo novo;
- cada registro possui uma identidade lógica (`business key`);
- alterações de conteúdo são detectadas por `content hash`;
- business key e content hash são gerados no backend;
- registros idênticos são ignorados;
- registros com a mesma identidade e conteúdo alterado são atualizados;
- erros de validação são registrados com contexto suficiente para diagnóstico;
- o módulo é recalculado após a persistência bem-sucedida dos dados.

## Business key e content hash

### Business key

Representa a identidade do registro no domínio.

Exemplo conceitual:

```text
businessKey = hash(campos estáveis que identificam o registro)
```

### Content hash

Representa o conteúdo mutável daquele registro.

```text
contentHash = hash(campos cujo valor pode mudar numa reimportação)
```

Com isso, o backend decide:

| Situação | Ação |
|---|---|
| business key nova | inserir |
| mesma business key + mesmo content hash | ignorar |
| mesma business key + content hash diferente | atualizar |

## Exemplo — RDO

Um relatório pode produzir mais de uma linha quando existem grupos ou disciplinas diferentes. Por isso, `relatorioId` sozinho não identifica o registro.

A identidade considera os campos definidos pelo módulo em `backend/app/modules/rdo/keys.py`.

O conteúdo mutável é tratado separadamente, permitindo atualizar status ou outros campos sem duplicar o registro.

## Upload direto de arquivos

RDO e RNC usam upload direto para o FastAPI:

```http
POST /api/v1/importacoes/{modulo}/arquivos
Content-Type: multipart/form-data
Idempotency-Key: <uuid>
```

O backend executa o processamento do arquivo, incluindo:

1. validação de quantidade e tamanho;
2. validação da assinatura do arquivo;
3. leitura do conteúdo;
4. normalização;
5. validação dos registros;
6. deduplicação dentro do envio;
7. geração de business key/content hash;
8. bulk upsert no PostgreSQL;
9. recálculo do módulo;
10. registro do job, arquivos processados e erros.

O processamento do envio é transacional: uma falha crítica impede a confirmação parcial indevida daquele envio.

### Formatos suportados

O backend possui suporte de parsing para formatos Excel/CSV usados pelos módulos que aceitam upload direto. A validação considera também a assinatura real do arquivo, não apenas a extensão.

Os limites de quantidade de arquivos, tamanho individual, tamanho total, número de linhas e concorrência são definidos em `backend/app/core/config.py` e podem ser configurados por variáveis de ambiente.

## Importação em lotes

A API também possui o fluxo de jobs em lotes, usado pelos módulos cujo tratamento atual envia registros normalizados para o backend:

```text
POST /api/v1/importacoes/iniciar
POST /api/v1/importacoes/{id}/lotes
POST /api/v1/importacoes/{id}/finalizar
```

O fluxo funciona assim:

1. cria o job de importação;
2. envia um ou mais lotes numerados;
3. valida e persiste cada lote;
4. contabiliza inseridos, atualizados, ignorados e rejeitados;
5. finaliza o job;
6. recalcula o módulo.

Esse fluxo faz parte da arquitetura atual da aplicação e continua disponível para os módulos que dependem dele.

## Resultado da importação

Os jobs registram, conforme o tipo de importação:

- total encontrado;
- total inserido;
- total atualizado;
- total ignorado;
- total rejeitado;
- arquivos processados;
- erros por linha/campo;
- duração e status do processamento.

## Histórico

Endpoints principais:

```text
GET /api/v1/importacoes
GET /api/v1/importacoes/{id}
GET /api/v1/importacoes/{id}/erros
```

A área de Administração exibe esse histórico para os perfis autorizados.

## Exclusão de dados administrativos

Os módulos operacionais expõem rotas de contagem e exclusão dos registros administrativos por período ou escopo permitido.

O padrão é:

```text
GET    /api/v1/<modulo>/registros
DELETE /api/v1/<modulo>/registros
```

A exclusão de registros administrativos não remove automaticamente a publicação vigente. Publicação e base administrativa são conceitos separados.

## Segurança e idempotência

No upload direto, `Idempotency-Key` evita reprocessamento acidental do mesmo envio quando a mesma tentativa é repetida.

No fluxo em lotes, a identificação do job e do número do lote evita processamento duplicado do mesmo lote.

## Onde está a implementação

```text
backend/app/modules/imports/
├── bulk_upsert.py
├── parsers/
├── registry.py
├── router.py
├── schemas.py
└── service.py
```

A lógica específica de cada módulo fica no respectivo pacote, em `backend/app/modules/<modulo>/`.
