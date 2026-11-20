# 12 — Seção Revisão (tela dividida 60/40, fila priorizada, divergências e atalhos)

Status: `pendente`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Decisões: [fluxos de revisão e divergências](../decisoes/09-fluxos-interface-web-revisao-consulta.md), [renderização Markdown + KaTeX](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md)

## Contexto

A seção **`Revisão`** é o workspace principal de curadoria humana do **Enade Questões**. Precisa equilibrar velocidade (aprovação em 1 clique ou atalho `A`, avanço automático) com rigor técnico (renderização fiel de código, tabelas e fórmulas KaTeX, ampliação de circuitos/figuras em lightbox, comparador lado a lado de `Divergência de Reclassificação` e transparência multi-taxonomia).

## Entrega observável

Workspace de `Revisão` operacional com 3 abas (`Pendentes`, `Divergências`, `Disciplina arquivada`), tela dividida 60/40, renderizador Markdown GFM + KaTeX sanitizado, lightbox de `Ativo Visual`s, ações de veredito e divergência, acordeão multi-taxonomia/histórico e atalhos de teclado.

## Escopo e limites

- **Renderizador técnico reutilizável (`frontend/src/components/markdown/`)**:
  - Renderização de **Markdown GFM** (tabelas, blocos de código com destaque de sintaxe) + **KaTeX** (`$...$` / `$$...$$`) estritamente sanitizada (bloqueando HTML arbitrário / XSS).
- **Fila e 3 abas (`frontend/src/features/revisao/`)**:
  - Abas **`Pendentes`** (ordenação `revisao_prioritaria → menor confianca → ano desc, numero asc`), **`Divergências`** e **`Disciplina arquivada`**, além do suporte ao modo **"Recorte filtrado"** vindo de `Questões` (com navegação `Anterior / Próxima` e contador `X de N`).
- **Coluna esquerda (~60%, rolável — leitura da `Questão`)**:
  - Cabeçalho com `Prova`/ano, `numero` oficial, situação do `Gabarito`/`ANULADA` e badges de `Alerta de Extração` (distinguindo críticos e informativos).
  - Enunciado em Markdown+KaTeX, galeria de `Ativo Visual`s com clique para lightbox em alta resolução, `Alternativa`s `A`–`E` (com destaque discreto para a correta e `Ativo Visual` vinculado quando existir) e botão **"Copiar questão em Markdown"**.
  - Ponto de encaixe limpo para o botão **"Editar conteúdo"** e **"Ver página do PDF"** entregues na Tarefa 13.
- **Coluna direita (~40%, fixa — veredito sob a `Taxonomia` ativa)**:
  - *Modo padrão*: exibe sugestão da IA (`Disciplina` principal, `0..2` secundárias, `Tópico`s, justificativa, confiança e banner de `revisao_prioritaria`), ações **Aprovar sugestão** (`POST .../aprovar`) e **Corrigir e aprovar** (`POST .../corrigir`, com seleção de 1 principal ativa, até 2 secundárias ativas e editor de `Tópico`s), avançando automaticamente para a próxima questão da fila.
  - *Sem classificação / já aprovada*: formulário manual direto + botão para disparar `Execução de Classificação` individual; quando já aprovada, exibe veredito vigente com botão **"Editar classificação"**.
  - *Modo `Divergências`*: **comparador lado a lado (Vigente humana × Candidata IA)** destacando exatamente o que mudou em `Disciplina` principal/secundárias, justificativa e `Execução de Classificação` de origem, com 3 ações: **Manter humana**, **Aceitar candidata** e **Editar manualmente**.
  - *Acordeão recolhido por padrão*: **"Outras taxonomias (N) e histórico"** exibindo classificações em outras `Taxonomia`s e histórico append-only (predição original da IA vs revisões humanas).
- **Atalhos de teclado**: `A` (aprovar), `E` (editar/corrigir), `←`/`→` (anterior/próxima) e `Esc` (fechar lightbox/edição), automaticamente desabilitados quando o foco estiver em `input`, `textarea` ou `select`.
- **Fora de escopo**: modo de edição de enunciado/alternativas/mídia e visualizador da página do PDF (Tarefa 13).

## Dependências

- [08 — API de Questões, busca textual/trigrama, revisão humana e edição de conteúdo/mídia](08-api-questoes-busca-revisao-edicao-midia.md)
- [09 — Shell global da SPA e seção Provas (Ingestão, Gabarito e Reprocessamento)](09-frontend-shell-e-ingestao-provas.md)

## Critérios de aceite

- [ ] Renderizador Markdown GFM + KaTeX exibe tabelas, blocos de código e fórmulas `$...$`/`$$...$$` e bloqueia scripts/HTML arbitrário (coberto por teste de sanitização).
- [ ] Aba `Pendentes` respeita a priorização, permite aprovar em 1 clique ou corrigir (1 principal + 0–2 secundárias) e avança automaticamente na fila atualizando o badge global.
- [ ] Aba `Divergências` exibe comparador lado a lado e executa `manter_humana`, `aceitar_candidata` e `editar_manualmente` via API.
- [ ] Acordeão "Outras taxonomias e histórico" mostra classificações de outras taxonomias e histórico imutável sem trocar de tela.
- [ ] Atalhos `A`, `E`, `←`/`→` e `Esc` funcionam no modo leitura e são ignorados com foco dentro de campos de formulário.
- [ ] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/components/markdown/` e `frontend/src/features/revisao/`.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

Pendente de execução.
