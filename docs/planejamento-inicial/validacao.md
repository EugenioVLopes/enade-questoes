# Validação ponta a ponta — Tarefa 15

Status: `verificação automatizada e E2E concluídas; aceite manual pendente`

Tarefa: [15 — validação E2E em provas reais](tarefas/15-validacao-e2e-provas-reais-e-documentacao.md) · Plano: [plano.md](plano.md) · Explicação: [explicacao.md](explicacao.md) · Pedido: [task.md](task.md)

Este documento registra o que foi executado de fato em 2026-11-25 (data da máquina de execução) contra as 3 provas oficiais reais de Engenharia de Computação (2017, 2019 e 2023). Todo número abaixo vem de um comando executado nesta validação. O que depende de olho humano no navegador está separado em [Pendente de aceite manual](#pendente-de-aceite-manual). Logs brutos ficaram em um diretório temporário fora do repositório e não são versionados; os comandos e as respostas relevantes estão reproduzidos neste documento.

## Ambiente e método

- Banco de desenvolvimento `enade_questoes` existente (PostgreSQL 16 do `compose.yaml`), reaproveitado por decisão da entrevista: 2017 entrou como Prova nova; 2019 e 2023 já existiam e foram reprocessadas, sem apagar dados e sem `sobrescrever_editadas=true`.
- Servidor: `cd backend && uv run uvicorn presentation.main:app --host 127.0.0.1 --port 8000`, **sem `--reload`** (reinício marca a ingestão como `interrompida`, `backend/src/application/worker.py:217-228`). O worker é uma thread daemon dentro do uvicorn (`worker.py:89`).
- Provedor LLM do `.env`: OpenRouter, modelo gratuito multimodal `nvidia/nemotron-3.5-super-vl:free`, `LLM_MAX_RPM=15`. Valores de chave não são registrados.
- Máquina: 14 GB de RAM. Suítes e ingestões rodaram em série, nunca ao mesmo tempo.
- Ordem: suítes (R0) → servidor → ingestão (2017, 2019, 2023) → casos de borda 2023 → classificação → revisão → busca → divergência → Gabarito/Reprocessar → `enade-eval`.

## Matriz critério → evidência → status

| # | Critério | Evidência | Status |
|---|---|---|---|
| C1 | `make lint`, `make test`, `make types` sem diff e `pnpm build` com exit 0 | [Suítes](#r0-suítes-automatizadas) | Verificado |
| C2 | Validação E2E nas 3 edições reais | [Ingestão](#r1-ingestão-real-das-3-edições), [casos de borda](#r2-casos-de-borda-reais-da-edição-2023), [fluxos](#r3-classificação-revisão-busca-divergência-e-gabarito), [`enade-eval`](#r4-cli-enade-eval) | Verificado em 2019 e 2023; **parcial em 2017** ([pendência Major](#pendência-major-extração-degradada-em-2017)); ressalvas em [Limitações](#limitações-e-divergências-encontradas) |
| C3 | Fluxos de `explicacao.md` reconciliados com o código | Responsabilidade do documento [explicacao.md](explicacao.md); aqui só se confirmam os fluxos em execução real | Verificado em execução; texto reconciliado fora deste arquivo |
| C4 | Ingestão real sem vazamento de memória do Docling, com alertas esperados (`pdf_via_ocr` 2017; `formula_nao_decodificada` e `formula_recorte` na Q13/2023; `fonte_symbol_detectada` na Q10/2023; `ANULADA` em 2019) | [Ingestão](#r1-ingestão-real-das-3-edições), [R2](#r2-casos-de-borda-reais-da-edição-2023), [Gabarito 2019](#gabarito-anulada-em-2019) | **Parcial**: a ingestão de 2017 terminou com `pdf_via_ocr`, mas com conteúdo degradado ([pendência Major](#pendência-major-extração-degradada-em-2017)); `ANULADA` de 2019 verificada no parser e no teste `enade_real`, sem Questão anulada persistida (0 no Componente Específico); memória medida externamente (ver limitações) |
| C5 | Fluxos de revisão, edição, divergências, busca e `enade-eval` | [R2](#r2-casos-de-borda-reais-da-edição-2023), [R3](#r3-classificação-revisão-busca-divergência-e-gabarito), [R4](#r4-cli-enade-eval) | Verificado via API e CLI (sem navegador). A Execução de Classificação de 2023 pela API reaproveitou o cache (1 chamada viva); a classificação multimodal ao vivo está comprovada pelo `enade-eval avaliar --no-cache` ([R3](#execução-de-classificação-2023-completa), [R4](#r4-cli-enade-eval)) |
| C6 | Backend (ruff, import-linter, pytest incluindo contrato de extração em `data/enade/`) e frontend (type-check, lint, test, build) | [Suítes](#r0-suítes-automatizadas) | Verificado |
| C7 | `enade-eval` com fakes na suíte e smoke real em amostra | Suíte (`make test`) e [R4](#r4-cli-enade-eval) | Verificado |
| C8 | Verificação manual no navegador com prova real ingerida | [Pendente de aceite manual](#pendente-de-aceite-manual) | Pendente |
| C9 | Itens de aceite visual/manual separados como pendentes | [Pendente de aceite manual](#pendente-de-aceite-manual) | Verificado (separação feita) |
| C10 | Checkpoint 3 e quatro seções funcionando | Depende do victory audit da Tarefa 10 ([pendência](#pendência-do-victory-audit-da-tarefa-10)) | Pendente |
| C11 | Critérios da fase de planejamento (`task.md`) | Os 7 itens do `task.md` já estão marcados; sem reexecução aqui | Referência |

Critérios do pedido original da Tarefa 15: suítes verdes (C1), 3 edições ingeridas com os alertas esperados e memória medida por ingestão (C4), edição da Q15, página do PDF, classificação, revisão, busca, divergência, Gabarito/Reprocessar e os 4 subcomandos do `enade-eval` com comando e saída (C5, C7), `validacao.md` criado (este arquivo) e aceite visual separado (C9).

## R0. Suítes automatizadas

| Comando | Exit | Resultado |
|---|---|---|
| `make lint` | 0 | `ruff check`: All checks passed; `ruff format --check`: 121 files already formatted; `lint-imports`: 3 contratos mantidos, 0 quebrados (118 arquivos, 612 dependências); `pnpm type-check` e `pnpm lint` sem erro |
| `make test` | 0 | pytest: **323 passed**, 0 skipped, 0 failed (124,85 s). Vitest: **15 arquivos, 175 testes passados** (12,70 s) |
| `make types` | 0 | sem erro |
| `git diff --exit-code frontend/src/api/schema.d.ts` | 0 | sem diff após `make types` |
| `cd frontend && pnpm build` | 0 | build concluído em 3,30 s; aviso de chunk acima de 500 kB (informativo) |
| `cd backend && uv run pytest -m enade_real -v -rs` | 0 | **7 passed**, 316 deselected, **0 skips** (78,51 s): os PDFs de `data/enade/` estavam presentes, então nenhum teste foi ignorado |

Observação: o `make test` roda o pytest sem filtro de marcador (`Makefile:31-33`), então os 7 testes `enade_real` fazem parte dos 323. Se os PDFs faltarem, esses testes pulam e a suíte continua verde; por isso o comando com `-rs` foi executado em separado para expor skips.

## R1. Ingestão real das 3 edições

### Estado inicial do banco (antes de ingerir)

`GET /api/v1/provas` devolveu apenas 2 Provas, ambas `concluida`:

| Ano | Questões | Gabarito (válidas/anuladas/pendentes) | Alertas abertos (críticos) |
|---|---|---|---|
| 2023 | 29 | 29 / 0 / 0 | 13 (5) |
| 2019 | 27 | 27 / 0 / 0 | 19 (8) |
| 2017 | não existia | — | — |

### Comandos

```bash
# 2017: Prova nova (curso exato das Provas existentes); gabarito enviado junto
curl -s -X POST http://127.0.0.1:8000/api/v1/provas \
  --form-string exame=ENADE --form-string curso="Engenharia de Computação" --form-string ano=2017 \
  -F "arquivo_prova=@data/enade/2017/prova_enade_2017_engenharia_computacao.pdf" \
  -F "arquivo_gabarito=@data/enade/2017/gabarito_enade_2017_engenharia_computacao.pdf"
# 2019 e 2023: reprocessar
curl -s -X POST http://127.0.0.1:8000/api/v1/provas/<prova_id>/reprocessar \
  -H 'Content-Type: application/json' -d '{"sobrescrever_editadas": false}'
```

Cada ingestão rodou sozinha (uma por vez). A memória foi medida por um amostrador externo (script em [Reproduzir](#reproduzir)): a cada 0,5 s ele localizava `pgrep -f infrastructure.extracao._worker` (subprocesso Docling, `backend/src/infrastructure/extracao/extrator_prova.py:203-232`) e guardava o maior `VmHWM` de `/proc/<pid>/status`; também registrou a `VmRSS` do processo uvicorn antes e depois. O código da aplicação **não** instrumenta memória (ver limitações).

### Resultados por edição (após a ingestão, antes das edições manuais)

| Item | 2017 (Prova nova) | 2019 (reprocessada) | 2023 (reprocessada) |
|---|---|---|---|
| Faixa do Componente Específico | Q09–Q35 | Q09–Q35 | Q10–Q38 |
| Questões | 27 | 27 | 29 |
| Alternativas (total) | 32 | 112 | 135 |
| Ativos Visuais `picture_docling` | 10 | 12 | 7 |
| Ativos Visuais `formula_recorte` | 6 | 3 | 5 |
| Alerta `pdf_via_ocr` (crítico) | 27 (todas as Questões) | 0 | 0 |
| Alerta `alternativas_incompletas` (crítico) | 27 | 6 (Q09, Q12, Q14, Q15, Q22, Q26) | 2 (Q13, Q15) |
| Alerta `formula_nao_decodificada` (crítico) | 2 (Q12, Q18) | 2 (Q15, Q32) | 3 (Q13, Q19, Q29) |
| Alerta `enunciado_suspeito` (crítico) | 6 (Q09, Q11, Q20, Q24, Q28, Q30) | 0 | 0 |
| Alerta `fonte_symbol_detectada` (informativo) | 10 | 11 | 8 |
| Alerta `gabarito_ausente_na_prova` | 0 | 0 | 0 |
| Situação do Gabarito nas Questões | 27 válidas | 27 válidas | 29 válidas |
| `usou_ocr` (metadado da Ingestão) | `true` | `false` | `false` |
| Imagens detectadas / filtradas na margem | 89 / 74 | 94 / 73 | 75 / 62 |
| Alertas abertos segundo `GET /provas`: total (dos quais críticos) | 72 (62) | 19 (8) | 13 (5) |
| Tempo `concluida_em - iniciada_em` | 151,2 s | 41,3 s | 41,3 s |
| Pico `VmHWM` do subprocesso Docling | 2.796 MB | 2.240 MB | 2.325 MB |
| `VmRSS` máxima do subprocesso | 2.700 MB | 2.125 MB | 2.239 MB |
| `VmRSS` do uvicorn antes → depois | 208 → 274 MB | 274 → 275 MB | 275 → 296 MB |

Uma quarta ingestão (2023 de novo, depois das edições e do Gabarito, na etapa de Reprocessar) levou 71,2 s, com pico `VmHWM` do Docling de 2.251 MB e `VmRSS` do uvicorn de 332 → 342 MB.

Contagens de `formula_recorte` por edição vêm dos Ativos Visuais (`origem`), não de alerta: `formula_recorte` é origem de Ativo Visual (`backend/src/domain/enums.py:35`). Os 6 casos de `formula_nao_decodificada` além da Q13/2023 (2017: 2; 2019: 2; 2023: Q19 e Q29) confirmam o risco já apontado na exploração: o alerta nasce do marcador `<!-- formula-not-decoded -->` no texto (`backend/src/domain/alertas_extracao.py:60-63`), então toda fórmula que o Docling devolve sem texto o dispara, e o recorte (`formula_recorte`) é gerado para toda fórmula com bbox.

### Memória e vazamento

- O subprocesso Docling alcançou entre 2,2 GB e 2,8 GB de pico (HWM) em cada ingestão. O valor de 2017 é o maior, coerente com o OCR de página inteira. Os picos não se acumulam entre ingestões: cada um é um processo novo, que termina e devolve a memória ao sistema operacional (o amostrador deixou de encontrar o PID depois de cada ingestão).
- A `VmRSS` do uvicorn, por ingestão (tabela acima): 1ª, 208 → 274 MB (+66 MB; o pós-processamento roda no processo do worker, `backend/src/infrastructure/extracao/extrator_prova.py:189-195`); 2ª, 274 → 275 MB (+1 MB); 3ª, 275 → 296 MB (+21 MB); entre o fim da 3ª e o início da 4ª, 296 → 332 MB (+36 MB, intervalo sem ingestão, com edições, classificação e `enade-eval`); 4ª, 332 → 342 MB (+10 MB). Saldo da sessão: 208 → 342 MB (+134 MB). Não há medição posterior a esse ponto.
- Leitura dos números: quatro pontos de `VmRSS` não bastam para distinguir acúmulo gradual de variação normal, e o crescimento fora das ingestões (+36 MB) não foi investigado. Não há indício de que os ~2,3 GB do Docling permaneçam no processo principal (o subprocesso termina a cada ingestão e o amostrador deixa de encontrá-lo), mas a ausência de vazamento no uvicorn não está demonstrada: apenas não foi observada nas quatro medições.

## Comandos dos fluxos de R2 e R3

Método, rota e status abaixo foram conferidos no log de acesso do uvicorn da execução. Os corpos JSON seguem os esquemas `EditarQuestaoRequest`, `CorrigirClassificacaoRequest` e `ResolverDivergenciaRequest` (`backend/src/presentation/api/schemas_questoes.py:193-233`) e `ExecucaoClassificacaoCriarRequest` (`backend/src/presentation/api/schemas.py:228-234`). Os textos longos transcritos das páginas (corpos dos `PATCH`) não são reproduzidos; aparecem o formato e, quando curtos, os valores enviados (nas correções e resoluções, valores conforme as respostas HTTP obtidas). Os filtros `jq` das variáveis são equivalentes aos usados (as mesmas rotas de listagem), mas o texto exato dos filtros não foi preservado.

```bash
BASE=http://127.0.0.1:8000
PROVA_2023=$(curl -s $BASE/api/v1/provas | jq -r '.itens[] | select(.ano==2023) | .id')
TAX=$(curl -s $BASE/api/v1/taxonomias | jq -r '.itens[] | select(.codigo=="enade-eng-computacao") | .id')
PERF=$(curl -s $BASE/api/v1/perfis-classificacao | jq -r '.itens[] | select(.codigo=="v2-fronteiras" and .versao=="v1") | .id')
# id da Questão de número N na Prova 2023 (usado para Q10, Q13, Q15, Q16, Q19, Q29, Q32 e demais)
q() { curl -s "$BASE/api/v1/questoes?prova_id=$PROVA_2023&tamanho_pagina=200" | jq -r ".itens[] | select(.numero==$1) | .id"; }
Q13=$(q 13); Q15=$(q 15); Q16=$(q 16); Q19=$(q 19); Q29=$(q 29); Q32=$(q 32)
```

R2: casos de borda (Prova 2023)

```bash
# Detalhe antes/depois: alertas_extracao, ativos_visuais, alternativas, versao        (GET 200)
curl -s $BASE/api/v1/questoes/$Q15
# Página original do PDF: 17 (Q13), 14 (Q10), 19 (Q15), 22 (Q19), 32 (Q29)            (GET 200, image/png)
curl -s -o pagina_17.png "$BASE/api/v1/provas/$PROVA_2023/paginas/17/imagem?dpi=150"
# Edição de Q13 e Q15 (PATCH 200): enunciado + 5 Alternativas transcritas + versao lida no GET (2 em ambas)
curl -s -X PATCH $BASE/api/v1/questoes/$Q15 -H 'Content-Type: application/json' -d @corpo_q15.json
#   corpo_q15.json = {"enunciado": "...", "alternativas": [{"letra":"A","texto":"..."}, ... {"letra":"E","texto":"..."}], "versao": 2}
# Edição de Q19 e Q29 (PATCH 200): só enunciado + versao (2 em ambas)
#   corpo = {"enunciado": "...", "versao": 2}
```

R3: classificação, Revisão, busca, divergência, Gabarito e Reprocessar

```bash
# 1ª Execução de Classificação: toda a Prova 2023                                      (POST 202, total_itens=29)
curl -s -X POST $BASE/api/v1/execucoes-classificacao -H 'Content-Type: application/json' \
  -d "{\"taxonomia_id\":\"$TAX\",\"perfil_id\":\"$PERF\",\"escopo\":\"prova_id\",\"prova_id\":\"$PROVA_2023\"}"
EXEC1=<execucao_id da resposta>
curl -s $BASE/api/v1/execucoes-classificacao/$EXEC1          # GET 200, repetido até o status final
curl -s -X POST $BASE/api/v1/execucoes-classificacao/$EXEC1/retomar   # POST 202 (Q23 falhou de novo)

# Aprovar sugestão, 23 Questões, sem corpo                                             (POST 200)
curl -s -X POST $BASE/api/v1/questoes/$QID/classificacoes/$TAX/aprovar
# Corrigir Disciplina principal: Q16, Q29 e Q32                                        (POST 201)
curl -s -X POST $BASE/api/v1/questoes/$Q16/classificacoes/$TAX/corrigir -H 'Content-Type: application/json' \
  -d '{"disciplina_principal":"sistemas-digitais-e-embarcados","disciplinas_secundarias":[],"topicos":[],"justificativa":"Registradores de bits em sistemas embarcados pertencem a Sistemas Digitais e Embarcados, nao a Algoritmos."}'
#   Q29: "disciplina_principal":"ia-e-ciencia-de-dados", justificativa "SVM e tecnica de aprendizado de maquina supervisionado."
#   Q32: "disciplina_principal":"ia-e-ciencia-de-dados", justificativa "Busca gulosa e busca heuristica, topico de IA."
#   (valores conforme as respostas 201 salvas; os campos secundárias e tópicos ficaram vazios)

# Busca e filtros: cada linha da tabela de busca é uma chamada                         (GET 200)
curl -s "$BASE/api/v1/questoes?q=memoria"
curl -s "$BASE/api/v1/questoes?q=mem%C3%B3ria&ano=2023&taxonomia_id=$TAX&status_revisao=aprovada"

# Reclassificação das 3 Questões corrigidas, incluindo revisadas                       (POST 202, total_itens=3)
curl -s -X POST $BASE/api/v1/execucoes-classificacao -H 'Content-Type: application/json' \
  -d "{\"taxonomia_id\":\"$TAX\",\"perfil_id\":\"$PERF\",\"escopo\":\"questao_ids\",\"questao_ids\":[\"$Q16\",\"$Q29\",\"$Q32\"],\"incluir_revisadas\":true}"
curl -s "$BASE/api/v1/questoes?prova_id=$PROVA_2023&taxonomia_id=$TAX&com_divergencia=true"   # GET 200
DIV16=$(curl -s "$BASE/api/v1/questoes/$Q16?taxonomia_id=$TAX" | jq -r '.divergencia_aberta.id')   # idem para Q29 e Q32
# Resolver Divergência de Reclassificação                                               (POST 200)
curl -s -X POST $BASE/api/v1/questoes/$Q16/divergencias/$DIV16/resolver -H 'Content-Type: application/json' \
  -d '{"resolucao":"manter_humana"}'
#   Q29: {"resolucao":"editar_manualmente","classificacao":{"disciplina_principal":"ia-e-ciencia-de-dados","disciplinas_secundarias":["algoritmos-e-estruturas-de-dados"],"topicos":[],"justificativa":"Resolucao manual da divergencia: SVM e IA, com algoritmos como secundaria."}}
#   Q32: {"resolucao":"aceitar_candidata"}   (depois, novo `corrigir` da Q32 para ia-e-ciencia-de-dados, POST 201)

# Gabarito independente (2 chamadas PUT 200 na Prova 2023) e Reprocessar sem sobrescrever editadas
curl -s -X PUT $BASE/api/v1/provas/$PROVA_2023/gabarito -F "arquivo_gabarito=@data/enade/2023/gabarito_enade_2023_engenharia_computacao.pdf"
curl -s -X POST $BASE/api/v1/provas/$PROVA_2023/reprocessar -H 'Content-Type: application/json' -d '{"sobrescrever_editadas": false}'   # POST 202
```

## R2. Casos de borda reais da edição 2023

Prova 2023, após reprocessar. IDs das Questões foram lidos de `GET /api/v1/questoes?prova_id=<id>`.

### Q13: fórmula não decodificada e recorte

- Antes: alertas `alternativas_incompletas` (crítico, aberto), `formula_nao_decodificada` (crítico, aberto) e `fonte_symbol_detectada` (informativo, aberto); Ativos Visuais `picture_docling` e `formula_recorte` (ambos na página 17); `alternativas` vazia; o enunciado terminava no marcador `<!-- formula-not-decoded -->`.
- Conferência da página original: `GET /api/v1/provas/<id>/paginas/17/imagem?dpi=150` (HTTP 200, `image/png`); a imagem foi aberta e lida. A "fórmula" não decodificada eram, na verdade, as cinco Alternativas A–E (equações com correntes `I`), que o Docling devolveu como imagem.
- Edição (`PATCH /api/v1/questoes/<id>` com `versao`): o marcador saiu do enunciado e as Alternativas A–E foram preenchidas em LaTeX transcrito da página, por exemplo `$I_1 + I_4 - I_5 = 0$ e $I_1 + I_2 + I_3 - I_5 = 0$` (A) até `$I_1 + I_2 - I_3 - I_5 = 0$ e $I_1 - I_3 + I_4 - I_6 = 0$` (E). Desvio em relação ao roteiro (substituir o marcador pela fórmula no enunciado): a equação era o conteúdo das Alternativas, então o texto foi para elas; assim os dois alertas fecham.
- Depois: `versao` 2 → 3 (a `versao` 5 vista mais adiante vem das chamadas de Gabarito, ver [Gabarito independente e Reprocessar](#gabarito-independente-e-reprocessar)), `editada_manualmente=true`, `alternativas_incompletas` e `formula_nao_decodificada` **resolvidos** (reavaliação determinística, `backend/src/domain/alertas_extracao.py:157`); o Ativo `formula_recorte` foi mantido; `fonte_symbol_detectada` segue aberto (informativo).

### Q10: fonte Symbol

- Alerta `fonte_symbol_detectada`, severidade informativa, status aberto, na página 14 (inspeção direta: `detectar_paginas_fonte_symbol` devolveu `(14, 16, 17, 21, 22, 26, 32)` no PDF completo de 2023). Nenhum alerta crítico na Q10 (Ativo `picture_docling` na página 14, 5 Alternativas).

### Q15: Alternativas vazias

- Antes: `alternativas_incompletas` crítico aberto; 0 Alternativas; o enunciado trazia as cinco Alternativas de código fundidas num bloco de código.
- Página lida: `GET .../paginas/19/imagem?dpi=150` (HTTP 200). As Alternativas A–E são cinco trechos de código C (`malloc`/`free`).
- Edição: `PATCH` com `versao`, enunciado reduzido ao texto da pergunta e as 5 Alternativas com o código real (bloco ```` ```c ````) transcrito da imagem, sem placeholder.
- Depois: `versao` 2 → 3, `editada_manualmente=true`, `alternativas_incompletas` **resolvido**, 5 Alternativas.

### Q19 e Q29: edições além do roteiro

Para que as Questões 19 e 29 pudessem entrar no Conjunto-Ouro (sem alerta crítico aberto), o marcador de fórmula foi trocado por LaTeX lido nas páginas 22 e 32: a gramática (`S → var = E; | var = E; S`, `E → E + E | ...`) e a sentença `a = a / (b - b);` na Q19, e a função por partes `f(i)` da SVM na Q29. Ambas passaram a `editada_manualmente=true` e tiveram `formula_nao_decodificada` resolvido. Efeito: 2023 passou de 5 para **0 alertas críticos abertos** (8 informativos abertos, todos `fonte_symbol_detectada`) e 4 Questões editadas (Q13, Q15, Q19, Q29).

## R3. Classificação, Revisão, busca, divergência e Gabarito

### Execução de Classificação (2023 completa)

`POST /api/v1/execucoes-classificacao` com `escopo=prova_id`, Taxonomia `enade-eng-computacao` (18 Disciplinas) e Perfil `v2-fronteiras@v1`.

- 1ª execução (pela API, com cache): `total_itens=29`, `processadas=29`, `total_erros=1`, status `concluida_com_erros`, 24 `cache_hits`, 110.245 tokens de prompt e 38.337 de resposta, de 21:35:26 a 21:41:43 (6 min 16 s). O erro foi em uma Questão (Q23): "Falha após 5 tentativa(s) no provedor 'openrouter': Resposta vazia do modelo (possível consumo total em thinking oculto)".
- Composição das 29 `processadas`: 25 sucessos (Q10 a Q38, exceto Q13, Q15, Q19 e Q23), 1 erro (Q23) e 3 puladas (Q13, Q15 e Q19, já `aprovada`; a Questão pulada entra em `processadas`, `backend/src/application/execucoes_classificacao.py:258-266`). Dos 25 sucessos, 24 vieram do cache; logo, **1 chamada ao vivo bem-sucedida**, mais as 5 tentativas falhas da Q23. Os tokens 110.245 e 38.337 não medem consumo dessa execução: o cache devolve os tokens da chamada original (`backend/src/infrastructure/llm/cliente_openai.py:343-346`).
- `POST .../retomar`: reexecutou a Questão com falha e terminou outra vez com `concluida_com_erros`, `total_erros=1`, o mesmo erro, às 21:48:32. A Q23 manteve a Classificação automática de uma execução anterior (de 22/11), então todas as 29 Questões ficaram com Classificação vigente; a da Q23 não vem desta execução.
- O que esta execução comprova: o fluxo ponta a ponta (API, worker, gravação das Classificações, Revisão). Não comprova a classificação multimodal ao vivo. Essa evidência vem do `enade-eval avaliar --no-cache` do [R4](#r4-cli-enade-eval): 30 Questões do Conjunto-Ouro avaliadas com **0 cache hits**, 29 com resposta válida (conclusão válida 96,67%), 129.096 tokens de prompt e 48.067 de resposta, latência média de 17,3 s.
- Pendência: a API de Execução não permite ignorar o cache. `ignorar_cache` existe no caso de uso (`backend/src/application/classificacao.py:344`) e é usado pelo `enade-eval` (`backend/src/application/avaliacao.py:580`, opção `--no-cache`), mas `ExecucaoClassificacaoCriarRequest` (`backend/src/presentation/api/schemas.py:228-234`) não tem esse campo. Sem esse campo, uma Execução por API sem cache exigiria ampliar a API (fora do escopo desta tarefa).
- Resultado: 26 Questões `pendente_revisao` e 3 `aprovada` (Q13, Q15 e Q19, aprovadas em execuções anteriores).

### Revisão

| Ação | Quantidade | Questões |
|---|---|---|
| Aprovar sugestão (`POST .../aprovar`, HTTP 200) | 23 | Q10, Q11, Q12, Q14, Q17, Q18, Q20–Q28, Q30, Q31, Q33–Q38 |
| Corrigir (`POST .../corrigir`, HTTP 201), Disciplina trocada | 3 | Q16 → `sistemas-digitais-e-embarcados`; Q29 → `ia-e-ciencia-de-dados`; Q32 → `ia-e-ciencia-de-dados` |
| Já `aprovada` antes da validação | 3 | Q13, Q15, Q19 |

Resultado: **29 de 29** Classificações vigentes `aprovada`. As correções seguem a ementa da Taxonomia: o modelo havia classificado Q16 (registradores de bits em sistemas embarcados), Q29 (SVM) e Q32 (busca gulosa/heurística) como `algoritmos-e-estruturas-de-dados`. A correção cria Classificação `origem=humana` e preserva a predição da IA.

### Busca e filtros (`GET /api/v1/questoes`)

| Consulta | Resultado |
|---|---|
| `q=memoria` (sem acento) | 12 Questões |
| `q=memória` (com acento) | 11 Questões (as mesmas, menos 2023/Q11) |
| `q=compilacao` e `q=compilação` | 2 Questões em ambos (2023/Q19, 2019/Q25) |
| `q=alocac` (trecho parcial, `pg_trgm`) | 1 Questão (2023/Q15): casa pelo Tópico `alocacao-dinamica` da Classificação vigente; o enunciado contém "alocada", que não contém "alocac" (conferido por `SELECT` no banco de desenvolvimento) |
| `q=Kirchh` (trecho parcial) | 1 Questão (2023/Q13) |
| `q=transistor` | 0 |
| `q=gramatca` (erro de digitação) | 0 |
| `q=memória` + `ano=2023` + `taxonomia_id` + `status_revisao=aprovada` | 8 Questões |
| `q=Kirchoff` + `prova_id` + `com_alerta_extracao=true` | 1 Questão (Q13) |
| `ano=2023` + `taxonomia_id` + `status_revisao=aprovada` + `situacao_gabarito=valida` + `com_divergencia=false` | 29 |
| `ano=2019` / `com_alerta_extracao=true&ano=2017` | 27 / 27 |

A diferença de 1 Questão entre "memoria" e "memória" vem da Q11, cujo enunciado contém a URL `https://memoria.rnp.br/...`: sem acento o `ILIKE` casa essa substring, e com acento a consulta `TSVECTOR` com `pt_unaccent` tokeniza a URL como um só termo (explicação inferida do código em `backend/src/infrastructure/persistence/repositorios.py:88-144`; não validada com `EXPLAIN`). Não é tratado como defeito.

### Reclassificação e Divergência

- `POST /api/v1/execucoes-classificacao` com `escopo=questao_ids` (Q16, Q29, Q32) e `incluir_revisadas=true`: `concluida`, 3 processadas, 0 erros, `divergencias_abertas=3`, 3 `cache_hits`. A Classificação humana permaneceu vigente e aprovada; a candidata da IA (`algoritmos-e-estruturas-de-dados`) ficou como Divergência aberta nas 3 Questões (`GET /api/v1/questoes?com_divergencia=true` devolveu Q16, Q29, Q32).
- Resoluções (`POST /api/v1/questoes/<id>/divergencias/<id>/resolver`, HTTP 200): Q16 `manter_humana` (vigente continua humana, `sistemas-digitais-e-embarcados`); Q29 `editar_manualmente` (humana, principal `ia-e-ciencia-de-dados` e secundária `algoritmos-e-estruturas-de-dados`); Q32 `aceitar_candidata` (vigente passou a `automatica`, `algoritmos-e-estruturas-de-dados`).
- Para não deixar o dado errado, a Q32 foi corrigida de novo depois da resolução (`corrigir` → `ia-e-ciencia-de-dados`, HTTP 201). Estado final: 0 Divergências abertas, 29 Classificações `aprovada`.

### Gabarito independente e Reprocessar

- `PUT /api/v1/provas/<id>/gabarito` com o PDF de 2023 (o log de acesso registra **duas** chamadas, ambas HTTP 200, na Prova 2023; só a resposta de uma foi guardada): `{"mantidas":29,"alteradas":0,"anuladas":0,"sem_correspondencia":[1,2,3,4,5,6,7,8,9],"questoes_sem_gabarito":[]}` (as Questões 1–9 são da Formação Geral, fora da faixa 10–38 ingerida). A resposta da outra chamada não foi guardada.
- Antes e depois de `POST .../reprocessar` com `{"sobrescrever_editadas": false}` (hash SHA-256 de enunciado + Alternativas, `editada_manualmente`, Classificação e alertas; a `versao` ficou fora do `diff`), para Q13, Q15, Q19, Q29 e Q10, comparados com `diff`: **idêntico**. Q13, Q15, Q19 e Q29 mantiveram o conteúdo editado, `editada_manualmente=true`, a Classificação aprovada e os alertas resolvidos. Q10 (não editada) manteve o mesmo conteúdo e a Classificação. A comparação cobre, da Classificação vigente, só a Disciplina principal e o status (não as secundárias nem os Tópicos).
- `versao`: fica fora da comparação porque muda a cada gravação (`backend/src/infrastructure/persistence/repositorios.py:652`). Depois da edição, Q13, Q15, Q19 e Q29 estavam em 3 e Q10 em 2; antes do Reprocessar, em 5 e 4, respectivamente (+2, coerente com as duas chamadas `PUT .../gabarito`: aumento inferido do código, sem log por gravação). O Reprocessar manteve 5 nas editadas (puladas) e subiu a Q10 de 4 para 5, sem mudar o conteúdo.
- Totais após o Reprocessar: 29 Questões, 4 editadas manualmente, 0 alertas críticos abertos.

### Gabarito `ANULADA` em 2019

O Componente Específico (Q09–Q35) não tem nenhuma Questão anulada: o `GET /api/v1/provas` e a ingestão registraram 27 válidas e 0 anuladas. A anulada de 2019 é a Questão 1 (Formação Geral), fora da faixa ingerida (Q09–Q35); por isso nenhuma Questão persistida tem `situacao_gabarito=anulada` (consulta no banco de desenvolvimento: 2017 e 2019 com 27 `valida`; 2023 com 29 `valida`). A verificação de `ANULADA` é, portanto, do parser e do teste `enade_real`, não do banco. Evidências: o parser real de Gabarito (`ExtratorGabaritoPdfPlumber.extrair`) executado nos 3 PDFs devolveu: 2017 → 35 entradas, 35 válidas, 0 anuladas; 2019 → 35 entradas, **1 anulada (Q1)** e 34 válidas; 2023 → 40 entradas, 38 válidas e 2 pendentes (as discursivas `***`). O teste `enade_real` correspondente (`backend/tests/integration/test_extracao_real.py:72-98`) passou. Em 2023 o `PUT` aplicou-se a 29 Questões, sem `ANULADA`.

## R4. CLI `enade-eval`

Executado a partir da raiz do repositório. Nada foi criado em `evals/` na raiz; a saída ficou em `data/app/evals/` (ignorado pelo Git).

```bash
uv run --project backend enade-eval exportar-ouro --taxonomia enade-eng-computacao \
  --saida data/app/evals/golden/enade-eng-computacao.json                      # exit 0
uv run --project backend enade-eval avaliar --ouro data/app/evals/golden/enade-eng-computacao.json \
  --perfil v2-fronteiras@v1                                                    # baseline, exit 0
uv run --project backend enade-eval avaliar --ouro data/app/evals/golden/enade-eng-computacao.json \
  --perfil v2-fronteiras@v1 --no-cache                                         # candidato, exit 0
uv run --project backend enade-eval comparar \
  "data/app/evals/20261125T215638Z_enade-eng-computacao_v2-fronteiras@v1_nvidia-nemotron-3.5-super-vl-free.json" \
  "data/app/evals/20261125T220832Z_enade-eng-computacao_v2-fronteiras@v1_nvidia-nemotron-3.5-super-vl-free.json"   # baseline e candidato, exit 1
uv run --project backend enade-eval historico --taxonomia enade-eng-computacao # exit 0
```

- `exportar-ouro`: "Conjunto-Ouro exportado: ... itens=30, edições=2", digest `cd7bc93d25a394f46f4b98b8a8cc8fa27760b4ac81c07c3bd8a56b6238c0bb9d`. São as 29 Questões de 2023 aprovadas e sem alerta crítico mais 1 Questão de 2019 (Q29/2019), aprovada em execução de classificação anterior (23/11) do banco de desenvolvimento e sem alerta crítico (por isso 2 edições). **Desvio de R4**, que previa o Conjunto-Ouro só com Questões de 2023: o `exportar-ouro` inclui toda Questão aprovada e elegível da Taxonomia, de qualquer edição. As outras 4 Questões de 2019 com Classificação aprovada (Q12, Q14, Q22 e Q26) ficaram de fora por terem `alternativas_incompletas` aberto.
- `avaliar` (baseline, com cache): 30 Questões; acurácia principal 86,67%; Macro-F1 88,05%; Jaccard médio das secundárias 90,00%; Exact Match 86,67%; conclusão válida 96,67%; validade na 1ª tentativa 93,33%; taxa de revisão prioritária 3,45% (= 1/29, valor 0,0345 em `camada3.taxa_revisao_prioritaria` do relatório; o denominador de 29 é inferido: as Questões com resposta válida, já que a Q23 não teve); erro em alta confiança (≥ 0,85) 10,34% (3/29); 129.096 tokens de prompt e 47.960 de resposta; 26 cache hits (86,67%); latência média 19,4 s, p95 69,6 s. Questões divergentes: Q16, Q29 e Q32 (as três corrigidas manualmente no passo de Revisão; o modelo respondeu `algoritmos-e-estruturas-de-dados`) e Q23 (resposta inválida do provedor).
- `avaliar --no-cache` (candidato): acurácia principal 90,00%; Macro-F1 93,33%; Jaccard 90,00%; Exact Match 83,33%; conclusão válida 96,67%; validade na 1ª tentativa 86,67%; taxa de revisão prioritária 3,45%; erro em alta confiança 6,90% (2/29); 129.096 / 48.067 tokens; **0 cache hits**; latência média 17,3 s, p95 47,6 s.
- `comparar baseline candidato`: **exit code 1** (gate PADRÃO **reprovado**). Resultado legítimo e esperado para estes dados: o piso estrutural exige conclusão válida de 100%, e ambas as execuções tiveram 96,67% (a Q23 sempre devolve resposta inválida do provedor gratuito), além de validade na 1ª tentativa de 86,67% (< 95%). Os deltas relativos foram favoráveis (acurácia +3,33 p.p.; Macro-F1 +5,28 p.p.). Ganho: Q29 (`algoritmos-e-estruturas-de-dados` → `ia-e-ciencia-de-dados`, com secundárias vazias). Regressão: Q11 (secundária `algoritmos-e-estruturas-de-dados` adicionada pelo candidato). Isso mostra o gate funcionando como desenhado: ele barra pelo piso mesmo quando as métricas relativas melhoram.
- `historico --taxonomia enade-eng-computacao`: perfil `v2-fronteiras@v1`, modelo "(não registrado)" (Classificações antigas sem modelo), total 34 Classificações, aprovação direta 31 (91,18%), correção da Disciplina principal 3 (8,82%), correção só das secundárias 0 (0,00%).

Os relatórios JSON e Markdown de cada `avaliar` ficaram em `data/app/evals/<timestamp>_enade-eng-computacao_v2-fronteiras@v1_nvidia-nemotron-3.5-super-vl-free.{json,md}` (baseline `20261125T215638Z`, candidato `20261125T220832Z`).

## Pendência Major: extração degradada em 2017

A ingestão de 2017 terminou com status `concluida`, mas o conteúdo extraído é inutilizável sem edição manual. Por decisão do usuário, o critério de ingestão de 2017 fica **parcial** na [matriz](#matriz-critério--evidência--status) e o defeito não foi corrigido nesta tarefa (bug de desenho do extrator; ampliação).

Fatos, lidos do banco de desenvolvimento (somente `SELECT`) após a ingestão e as edições:

| Questões 2017 | Observação |
|---|---|
| Q9, Q11, Q20, Q24, Q28, Q30 | enunciado "dos Estudantes" (14 caracteres), 0 Alternativas, `enunciado_suspeito` aberto |
| Q15, Q17 | enunciado "2017  dos Estudantes" (20 caracteres), 0 Alternativas, **sem** `enunciado_suspeito`: 20 caracteres passam os limites de 15 caracteres e 8 alfanuméricos (`MIN_CHARS_ENUNCIADO_PADRAO` e `MIN_ALFANUMERICOS_ENUNCIADO_PADRAO`, `backend/src/domain/alertas_extracao.py:16-17`; verificação em `:76-87`) |
| Q10 | o enunciado começa com o texto da Q9 ("A figura a seguir representa o diagrama de tensão..."), contém as alternativas da Q9 e o caractere `日` (posição 506 do enunciado), seguido do texto da Q10; só 4 Alternativas (A–D) |
| Total | 32 Alternativas em 27 Questões: 18 Questões sem Alternativa, 9 com 2 a 4 e nenhuma com 5; 27 `alternativas_incompletas` abertos |

O teste `enade_real` de 2017 não cobre isso: `backend/tests/integration/test_extracao_real.py:218-222` aceita a contaminação, pois a palavra "diagrama" no enunciado da Q10 vem do texto da Q9 e as demais asserções só excluem `\x04` e "ĮŐƵƌĂ". Causa não investigada (hipótese não verificada: segmentação sobre texto de OCR de página inteira, com cabeçalho de página tratado como enunciado).

Reprodução (somente leitura; o `POST /api/v1/provas` repetido devolve 409 porque a Prova já existe, `backend/src/application/provas.py:201-203`; para reexecutar a extração use `POST /api/v1/provas/<id>/reprocessar`):

```bash
docker exec enade-questoes-postgres-1 psql -U enade -d enade_questoes -c "
SELECT q.numero, length(q.enunciado) AS caracteres, left(replace(q.enunciado, E'\n', ' '), 30) AS inicio,
       (SELECT count(*) FROM alternativas a WHERE a.questao_id = q.id) AS alternativas,
       (SELECT string_agg(al.codigo || '/' || al.status, ',') FROM alertas_extracao al
         WHERE al.questao_id = q.id AND al.codigo = 'enunciado_suspeito') AS suspeito
FROM questoes q JOIN provas p ON p.id = q.prova_id WHERE p.ano = 2017 ORDER BY q.numero"
docker exec enade-questoes-postgres-1 psql -U enade -d enade_questoes -c "
SELECT position('日' IN q.enunciado) AS posicao_cjk FROM questoes q JOIN provas p ON p.id = q.prova_id
WHERE p.ano = 2017 AND q.numero = 10"     # esperado hoje: 506
```

Critério de fechamento: nenhum enunciado de 2017 com menos de 15 caracteres, Q10 sem texto da Q9 nem `日`, e Alternativas A–E nas Questões objetivas (ou `alternativas_incompletas` apenas onde a página realmente não as tem), com asserções correspondentes no teste `enade_real`.

## Limitações e divergências encontradas

1. **Memória medida de fora.** O código não registra memória nem tempo por etapa (só `iniciada_em` e `concluida_em`, `backend/src/infrastructure/persistence/models.py:71-72`). Os picos acima vêm de um amostrador de 0,5 s sobre `/proc/<pid>/status` (script em [Reproduzir](#reproduzir)). O `VmHWM` é mantido pelo kernel e registra o pico real do processo observado; o amostrador pode perder apenas leituras intermediárias da `VmRSS` (logo, a `VmRSS` máxima), não o `VmHWM`. Instrumentar a aplicação ficou fora do escopo.
2. **`pdf_via_ocr` em todas as Questões de 2017** (27 de 27): o flag vem da inspeção do PDF inteiro (`backend/src/domain/alertas_extracao.py:133`), por desenho. Isso marca todas como revisão prioritária e bloqueia a exportação para o Conjunto-Ouro até a inspeção manual. A edição 2017 não entrou no Conjunto-Ouro (decisão da entrevista: só 2023).
3. **Extração de 2017 com OCR degradada (Major).** Enunciados truncados, Questões misturadas e só 32 Alternativas para 27 Questões. Detalhes, reprodução e critério de fechamento em [Pendência Major: extração degradada em 2017](#pendência-major-extração-degradada-em-2017). Não corrigida aqui (fora do escopo de correção cirúrgica).
4. **`formula_nao_decodificada` além da Q13/2023.** 2017: 2 Questões; 2019: 2; 2023: 3 (Q13, Q19 e Q29). Em 2019 (Q15 e Q32) e 2017 (Q12 e Q18) o alerta permanece aberto, sem edição.
5. **Questão 23/2023 sem resposta válida do provedor gratuito.** Falhou 5 tentativas na 1ª execução, de novo no `retomar` e no `enade-eval avaliar` (as duas vezes, 96,67% de conclusão). A Q23 mantém uma Classificação de execução antiga, que foi aprovada. Pode ser limite do modelo gratuito (resposta vazia, possível consumo em raciocínio oculto), sem causa confirmada.
6. **Cache e custo real.** Na 1ª Execução de Classificação, 24 dos 25 sucessos vieram do cache (1 chamada ao vivo bem-sucedida); só o `avaliar --no-cache` (30 Questões, 0 cache hits) mede o provedor sem cache. A API de Execução não tem opção para ignorar o cache (ver [R3](#execução-de-classificação-2023-completa)).
7. **Dados prévios no banco de desenvolvimento.** Q13, Q15 e Q19/2023 já tinham Classificação `aprovada` de execuções anteriores (a execução as pulou); o Conjunto-Ouro inclui 1 Questão de 2019 aprovada antes (desvio de R4, ver [R4](#r4-cli-enade-eval)). A validação não apagou esses dados.
8. **Contadores de `GET /api/v1/questoes`** (`pendentes`, `divergencias`, `disciplina_arquivada`) são globais e ignoram filtros (exemplo: `pendentes=75` com `prova_id` de 2023). Já listado entre as divergências de Tarefa 11.
9. **`evals/` na raiz não é ignorado pelo Git** (`.gitignore` só cobre `data/`). O padrão de `exportar-ouro` e do alvo `make golden-export` grava em `evals/golden/<taxonomia>.json`, relativo ao diretório atual. A execução usou `--saida data/app/evals/golden/...`. Decidir depois se `.gitignore` deve cobrir `evals/`; não foi alterado nesta tarefa.
10. **Correções pequenas no código:** nenhuma foi necessária; nenhum arquivo de `backend/src`, `backend/tests` ou `frontend/src` foi alterado nesta validação.
11. **Resolução `aceitar_candidata` e edição de Questões** tocam dados de desenvolvimento (Q32 foi corrigida de volta). O banco de desenvolvimento reflete essas edições; as 4 Questões editadas de 2023 (Q13, Q15, Q19, Q29) são transcrições feitas a partir das imagens das páginas, sem revisão de terceiros.
12. **Aceite pelo navegador não foi feito:** toda a verificação desta seção foi por API, CLI e leitura de imagens de página. A imagem da página 17 (Q13) e da 19 (Q15) foi aberta e lida; nenhuma tela da SPA foi exercitada.

## Resumo de divergências fora do escopo das Tarefas 10–13

Já registradas nas seções "Evidências e pendências" das tarefas (não bloqueiam esta tarefa; ficam para um ciclo futuro):

- **Tarefa 10:** `divergencias_abertas` nunca decrementa na Execução (`backend/src/domain/classificacao.py:344-345`); a pílula do worker não filtra por Taxonomia; o indicador de disciplina arquivada só existe na API de Questões; guardas sem teste discriminante; Prettier ausente.
- **Tarefa 11:** paginação usa o total da resposta anterior durante o recarregamento; histórico com `replace` não restaura filtros de outra Taxonomia; Ano órfão deixa o seletor vazio; padrões de código não aplicados (TODAS duplicada, `SITUACOES` sem `Record`, `FLAGS` repetindo `FLAG_KEYS`); contadores globais ignoram filtros.
- **Tarefa 12:** a aba Divergências usa `ordenacao=consulta` (a API não ordena por Execução mais recente); `questao=<id>` fora do recorte ainda é exibida; as setas descartam edição sem confirmação com o foco fora do formulário; imagens Markdown remotas.
- **Tarefa 13:** banner sem feedback em `isError`; `exigirAlternativa` por tipo; `aria-controls`/`role="tabpanel"`; capitalização de rótulos; subtítulo redundante.
- **Tarefas 09, 12 e 13:** não registram victory audit (lacuna documental).

## Pendência do victory audit da Tarefa 10

A [Tarefa 10](tarefas/10-frontend-taxonomias-perfis-execucoes.md) segue `em andamento`: a implementação foi verificada pelo gate, mas o victory audit foi interrompido e não há veredito `VICTORY CONFIRMED`. Por decisão da entrevista desta tarefa, seguiu-se adiante e a pendência fica registrada. Consequência: o Checkpoint 3 do [plano](plano.md) (quatro seções funcionando) não fecha até o audit ser reexecutado.

## Pendente de aceite manual

Nada abaixo foi executado nesta validação. Depende de confirmação explícita do usuário, com os fluxos abertos no navegador contra o backend e o PostgreSQL reais (por exemplo `make dev` com as Provas já ingeridas):

- **Tarefa 09:** shell e ingestão de Provas no navegador (Checkpoint 3).
- **Tarefa 10:** Taxonomias, Perfis e Execuções.
- **Tarefa 11:** consulta de Questões (filtros, busca, paginação).
- **Tarefa 12:** Revisão e divergências, incluindo `Esc` com o lightbox e a edição abertos.
- **Tarefa 13:** edição de conteúdo, mídia e PDF.
- **Visual:** proporção 60/40 da tela de Revisão (`frontend/src/features/revisao/RevisaoPage.tsx:540`) e o lightbox de imagens.
- **Mermaid:** renderização dos diagramas de [explicacao.md](explicacao.md) (o `mmdc` não está disponível; há um comentário de validação pendente no próprio documento).
- **Plano:** revisão visual e funcional de Provas, Taxonomias, Questões, Revisão e edição, prevista em [plano.md](plano.md) (seção "Verificações planejadas", linhas 138-139).
- **Aceite final do usuário** sobre esta Tarefa 15.

## Reproduzir

```bash
make lint && make test && make types && git diff --exit-code frontend/src/api/schema.d.ts
(cd frontend && pnpm build)
(cd backend && uv run pytest -m enade_real -v -rs)
make db-up && make migrate && make seed
(cd backend && uv run uvicorn presentation.main:app --host 127.0.0.1 --port 8000)   # sem --reload
# ingestão 2017 e reprocessar 2019/2023: seção "R1 > Comandos"
# edição, classificação, Revisão, busca, divergência, Gabarito e Reprocessar: seção "Comandos dos fluxos de R2 e R3"
# enade-eval: seção "R4"
```

Amostrador de memória usado em cada ingestão (`python3 amostrador.py <prova_id> <arquivo_com_pid_do_uvicorn> <saida.json>`, iniciado logo antes do `POST`/Reprocessar; a cada 0,5 s procura o subprocesso Docling e guarda o maior `VmHWM` e a maior `VmRSS` de `/proc/<pid>/status`, até a Ingestão sair de `pendente`/`processando`):

```python
import json, os, subprocess, sys, time, urllib.request

prova, arq_pid, saida = sys.argv[1], sys.argv[2], sys.argv[3]
uvicorn_pid = int(open(arq_pid).read())

def status(pid, chave):  # valor em kB de VmRSS ou VmHWM
    try:
        for linha in open(f"/proc/{pid}/status"):
            if linha.startswith(chave):
                return int(linha.split()[1])
    except Exception:
        pass
    return 0

def filhos_docling():
    pids = subprocess.run(["pgrep", "-f", "infrastructure.extracao._worker"], capture_output=True, text=True).stdout.split()
    return [int(p) for p in pids if int(p) != os.getpid()]

pico_hwm = pico_rss = 0
visto = False
t0 = time.time()
rss_antes = status(uvicorn_pid, "VmRSS:")
while True:
    for pid in filhos_docling():
        pico_hwm = max(pico_hwm, status(pid, "VmHWM:"))
        pico_rss = max(pico_rss, status(pid, "VmRSS:"))
        visto = True
    try:
        d = json.load(urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/provas/{prova}"))
        st = d["ultima_ingestao"]["status"]
        if st in ("concluida", "erro", "interrompida"):
            break
    except Exception:
        st = "?"
    if time.time() - t0 > 1500:
        break
    time.sleep(0.5)

json.dump({"prova": prova, "status": st, "wall_s": round(time.time() - t0, 1), "worker_visto": visto,
           "worker_VmHWM_MB": round(pico_hwm / 1024), "worker_VmRSS_max_MB": round(pico_rss / 1024),
           "uvicorn_RSS_antes_MB": round(rss_antes / 1024), "uvicorn_RSS_depois_MB": round(status(uvicorn_pid, "VmRSS:") / 1024),
           "uvicorn_HWM_MB": round(status(uvicorn_pid, "VmHWM:") / 1024)}, open(saida, "w"))
```

O tempo da Ingestão (`concluida_em - iniciada_em`) vem da tabela de ingestões (`backend/src/infrastructure/persistence/models.py:71-72`). Não rode a suíte completa e a ingestão real ao mesmo tempo: o Docling usa ~2,3 GB de RAM por ingestão.
