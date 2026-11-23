# 12 — Seção Revisão (tela dividida 60/40, fila priorizada, divergências e atalhos)

Status: `concluida`

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

- [x] Renderizador Markdown GFM + KaTeX exibe tabelas, blocos de código e fórmulas `$...$`/`$$...$$` e bloqueia scripts/HTML arbitrário (coberto por teste de sanitização).
- [x] Aba `Pendentes` respeita a priorização, permite aprovar em 1 clique ou corrigir (1 principal + 0–2 secundárias) e avança automaticamente na fila atualizando o badge global.
- [x] Aba `Divergências` exibe comparador lado a lado e executa `manter_humana`, `aceitar_candidata` e `editar_manualmente` via API.
- [x] Acordeão "Outras taxonomias e histórico" mostra classificações de outras taxonomias e histórico imutável sem trocar de tela.
- [x] Atalhos `A`, `E`, `←`/`→` e `Esc` funcionam no modo leitura e são ignorados com foco dentro de campos de formulário.
- [x] `pnpm type-check`, `pnpm lint`, `pnpm test` e `pnpm build` passam sem erro.

## Verificação

- Testes Vitest + Testing Library em `frontend/src/components/markdown/` e `frontend/src/features/revisao/`.
- `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Evidências e pendências

**Implementação**:
- **Renderizador técnico reutilizável (`frontend/src/components/markdown/`)**: `MarkdownContent.tsx` e `linguagens.ts` usando `react-markdown`, `remark-gfm`, `remark-math`, `rehype-katex` e `rehype-highlight`, com HTML bruto desabilitado e CSS do `katex` alinhado em `frontend/src/main.tsx`.
- **Seção `Revisão` (`frontend/src/features/revisao/`)**:
  - `RevisaoPage.tsx` (rota `revisao` em `frontend/src/app/router.tsx`, removendo `PlaceholderSectionPage.tsx`), `revisaoUrl.ts` (3 abas `Pendentes`, `Divergências`, `Disciplina arquivada` + modo `modo=recorte` integrado com `frontend/src/features/questoes/filtrosUrl.ts` e `frontend/src/components/layout/useTaxonomia.ts`), `QuestaoLeitura.tsx`, `GaleriaAtivos.tsx`, `questaoMarkdown.ts` (cópia da questão em Markdown), `PainelVeredito.tsx`, `FormularioClassificacao.tsx`, `ComparadorDivergencia.tsx`, `ResumoClassificacao.tsx`, `OutrasTaxonomiasHistorico.tsx`, `classificacaoUtils.ts` e `useAtalhosRevisao.ts`.
  - Ponto de encaixe `renderAcoesQuestao` em `RevisaoPage.tsx` reservado para os botões da Tarefa 13 ("Editar conteúdo" e "Ver página do PDF").
- **Cliente HTTP (`frontend/src/api/`)**: `revisao.ts` (detalhe da questão, fila infinita de 200 itens por página, mutations `aprovar`, `corrigir` e `resolver` invalidando `queryKeys.questoes.all`) e `queryKeys.ts`.
- **Backend (mudança mínima, autorizada)**: `backend/src/application/revisao.py` permite criar classificação humana via `POST /corrigir` quando a questão ainda não possui classificação vigente; `backend/src/presentation/api/app.py` traduz conflito de índice de vigente em HTTP 409; testes de integração em `backend/tests/integration/test_api_revisao_divergencias.py`.

**Correções de verificação e regressões (iterações 1–4)**:
- G1–G9 (r2): exclusão automática da nova principal dentre as secundárias; preservação de troca de aba durante veredito pendente; recarga de detalhe/fila em 409; reinício do formulário ao trocar de Taxonomia; alinhamento da versão do `katex`; remoção de `PlaceholderSectionPage.tsx` e ajustes de acessibilidade/glossário.
- K1–K5 (r3): preservação do formulário em 409/422; limpeza de `editandoId` ao trocar questão/Taxonomia; remoção de exports sem uso em `api/revisao.ts`; extração de `buscarProximaPagina` e limpeza de `id` órfão.
- L1–L4 (r4): fixação imediata de `questao=<idAtual>` em erro de veredito (inclusive sob `v7_startTransition`) mantendo questão, erro, formulário e navegação coerente (`Fora da fila · N na fila` com `Próxima` levando ao primeiro item); instância única de `FormularioClassificacao` com key estável para criação (`!vigente`) e edição (`editando`), preservando digitação em refetch/409; atalhos ignorando `evento.repeat`; guarda síncrona via `useRef` contra duplo veredito no mesmo tick; remoção de `export` sem uso de `ResolverDivergenciaResponse` e reuso de `idsDaFila(fila.data)`.

**Verificação executada**:
- `frontend/`: `pnpm type-check`, `pnpm lint`, `pnpm build` (exit 0) e `pnpm test` (exit 0 — 13 arquivos, 146 testes passando, incluindo 35 em `RevisaoPage.test.tsx`, 6 em `MarkdownContent.test.tsx`, 8 em `revisaoUrl.test.ts`, 2 em `questaoMarkdown.test.ts` e 1 em `PainelVeredito.test.tsx`).
- Raiz: `make lint` (exit 0).
- `backend/`: `uv run pytest` (exit 0 — 311 passed).

**Pendências registradas**:
- Validação manual no navegador contra o backend real (incluindo `Esc` com lightbox + edição abertos) fica para a Tarefa 15.
- Aba `Divergências` usa `ordenacao=consulta` porque a API atual não ordena por execução mais recente.
- `questao=<id>` fora do recorte ainda é exibida; setas descartam edição sem confirmação quando o foco está fora do formulário; imagens Markdown remotas dependem de política futura se necessário.
