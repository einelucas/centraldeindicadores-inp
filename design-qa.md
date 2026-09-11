# Design QA — Painel Geral do Scorecard

- Source visual truth: screenshots do painel original e da primeira implementação anexados pelo usuário nesta conversa; implementação de referência em `src/features/dashboard/components/DashboardOverview.tsx` e estilos em `src/app/globals.css`.
- Implementation screenshot: indisponível — o navegador integrado não está disponível nesta sessão.
- Viewport: referência original em 1764 × 405 px; viewport da implementação não capturado.
- Density normalization: não aplicada; a densidade da imagem de referência não foi informada e não houve captura da implementação.
- State: Painel Geral com dados publicados e período operacional selecionado.
- Primary interactions tested: validação estática do seletor, botão de atualização e links mensais; teste no navegador bloqueado.
- Console errors checked: bloqueado sem navegador integrado.

## Full-view comparison evidence

A captura enviada pelo usuário evidenciou rolagem horizontal no desktop e tipografia azul/cinza na tabela. A referência original evidencia a tabela contida no card e texto preto, exceto nos estados semânticos verde e vermelho. A comparação pós-correção permanece bloqueada porque não foi possível capturar a implementação renderizada.

## Focused-region comparison evidence

Não foi possível produzir evidência pós-correção dos cards, tabela e legendas. A inspeção de código confirma: tabela fluida sem largura mínima no desktop; rolagem restrita a viewports de até 900 px; texto preto como padrão; e verde/vermelho restritos aos valores e estados semânticos.

## Findings

- [Corrigido — P2] A tabela excedia o card no desktop por manter largura mínima e elementos internos largos.
- [Corrigido — P2] Textos neutros da tabela usavam azul e cinza em vez de preto.
- [Corrigido — P1] O Atendimento geral usava a escala setorial de cinco faixas. A escala agora é: vermelho abaixo de 70%; amarelo de 70% a 94,99%; verde a partir de 95%.
- A fidelidade visual final não pode ser aprovada sem uma captura renderizada no mesmo estado da referência.

## Comparison history

- Passagem 1: implementação concluída e validada por lint, typecheck e build; comparação visual bloqueada pela indisponibilidade do navegador integrado.
- Passagem 2: a captura do usuário revelou rolagem, cores tipográficas e classificação incorretas; os três pontos foram corrigidos. Os limites 69,99, 70, 94,99 e 95 foram executados diretamente contra a função de classificação e retornaram, respectivamente, vermelho, amarelo, amarelo e verde. A evidência visual pós-correção segue bloqueada.
- Passagem 3: a tipografia compactada da migração foi comparada com os estilos-fonte do original. O corpo da tabela voltou de 11 px para 14 px, o cabeçalho de 9 px para 11 px e os valores mensais de 10 px para 12 px; paddings, pesos e line-heights também foram restaurados. Um `colgroup` com as proporções originais passou a controlar o encaixe sem reduzir o texto. Lint, typecheck e build passaram; a captura visual pós-correção segue bloqueada pela indisponibilidade do navegador integrado.

## Follow-up polish

- Repetir a captura em desktop e mobile quando o navegador integrado estiver disponível e ajustar apenas diferenças visíveis de espaçamento, tipografia ou proporção.

final result: blocked
