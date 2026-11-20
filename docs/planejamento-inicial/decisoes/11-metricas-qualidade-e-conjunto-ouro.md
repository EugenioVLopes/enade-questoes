# Definir métricas de qualidade e conjunto-ouro (golden set) de classificação

Type: grilling
Status: resolved
Blocked by: 06, 07

## Question

Agora que [Definir modelo de domínio extensível e glossário (GLOSSARY.md)](./06-modelo-de-dominio-e-glossario.md) preservou intacta a saída original da IA ao lado das correções humanas e [Definir estratégia de classificação multimodal, reclassificação e validação](./07-estrategia-classificacao-e-reclassificacao.md) validou a classificação multimodal em 14 questões reais do ENADE 2023 (mostrando que `confianca` do LLM é superestimada e que variações entre perfis/modelos afetam principalmente as `disciplinas_secundarias`):

1. Como formar e manter o **conjunto-ouro (golden set)** na v1 (ex.: exportado a partir das `Classificação`s revisadas/aprovadas por humano em 1–3 edições do ENADE, ou mantido como fixture versionado)?
2. Quais **métricas objetivas** devem avaliar um novo `Perfil de Classificação` ou novo modelo/provedor (ex.: acurácia exata na `disciplina_principal`, F1/Jaccard no conjunto de `disciplinas_secundarias`, taxa de `revisao_prioritaria` e matriz de confusão entre fronteiras)?
3. Qual protocolo simples (CLI/comando local) usaremos para comparar regressões antes de promover um novo perfil ou migrar para o servidor **Qwen/vLLM** futuro?

## Answer

### 1. Formação, versionamento e elegibilidade do `Conjunto-Ouro`

- **Origem e armazenamento versionado**: o `Conjunto-Ouro` nasce diretamente das `Classificação`s revisadas e aprovadas por humano na interface `Revisão` e é exportado via CLI local (`enade-eval exportar-ouro`) para um arquivo JSON enxuto versionado no Git em `evals/golden/<taxonomia_codigo>.json` (um `Conjunto-Ouro` por `Taxonomia`).
- **Desacoplamento de UUIDs e mídia**: cada entrada referencia a `Questão` exclusivamente por chave natural `(exame, curso, ano, numero)` acompanhada de `disciplina_principal`, `disciplinas_secundarias`, `situacao_gabarito` e `notas` opcionais — sem duplicar PDFs nem `Ativo Visual`s no Git (que permanecem em `DATA_DIR` e PostgreSQL). O cabeçalho do snapshot registra `versao_schema`, `taxonomia_codigo`, data de exportação e contagem de itens/edições.
- **Critérios de elegibilidade e cobertura progressiva**:
  - Somente `Questão`s com `Classificação` vigente `status = aprovada` sob a `Taxonomia` alvo e **zero `Alerta de Extração` crítico aberto** (separando falhas de extração/OCR não curadas da qualidade do classificador).
  - Questões `ANULADA`s entram normalmente caso tenham sido revisadas com enunciado íntegro (com `situacao_gabarito` preservada no snapshot para inspeção).
  - Operável desde a **1ª edição completa revisada (~27–29 questões)** e expansível incrementalmente até as **3 edições locais do INEP (~83 questões de 2017, 2019 e 2023)**, sem travar os primeiros ciclos de avaliação.
- **Validação prévia (*preflight*) obrigatória**: antes de disparar qualquer chamada ao LLM, o CLI valida que todas as `Questão`s do `Conjunto-Ouro` existem no PostgreSQL local, não possuem `Alerta de Extração` crítico aberto e apontam apenas para `Disciplina`s **ativas** na `Taxonomia` alvo. Havendo qualquer inconsistência (ex.: após arquivar uma `Disciplina`), o comando aborta com a lista exata de itens defasados para revisão e reexportação, evitando desperdício de cota de API.

### 2. Pacote determinístico de métricas objetivas (3 camadas, sem *LLM-as-a-judge*)

Toda `Avaliação de Classificação` calcula métricas 100% determinísticas (ignorando `Tópico`s livres, que variam textualmente mesmo em `temperature=0`):

1. **Acurácia Curricular**:
   - **Acurácia exata na `Disciplina` principal** (`acertos / total`);
   - **Macro-F1 na `Disciplina` principal** (média não ponderada entre as disciplinas presentes no `Conjunto-Ouro`, impedindo que classes frequentes mascarem erro em disciplinas raras);
   - **Jaccard médio e F1 médio nas `Disciplina`s secundárias** (definindo `∅ == ∅ → 1.0`, evitando penalizar questões corretamente classificadas sem secundárias);
   - **Exact Match combinado**: acerto simultâneo de `disciplina_principal` e do conjunto exato `set(disciplinas_secundarias)`.
2. **Diagnóstico de Fronteiras**:
   - **Matriz de confusão** com ranking dos pares `esperada → predita` mais frequentes na `Disciplina` principal (alimentando diretamente ajustes no `guia_fronteiras` do `Perfil de Classificação`);
   - **Lista detalhada de divergências por `Questão`** (`(ano, numero)`, esperado vs predito, confiança, `revisao_prioritaria` e trecho da justificativa).
3. **Saúde Operacional & Calibração**:
   - **Taxa de conclusão válida** (após retry corretivo) e **taxa de validade estrutural na 1ª tentativa** (sem retry nem saneamento pós-LLM);
   - **Taxa de `revisao_prioritaria`**;
   - **Taxa de erro em alta confiança (`confianca >= 0,85`)**, expondo superconfiança sistemática do modelo;
   - **Custo e desempenho**: tokens de entrada/saída, taxa de acerto do cache LLM e latência média/p95 por questão.

### 3. Protocolo local via CLI (`enade-eval` / `Makefile`) e critérios de promoção

- **Superfície exclusiva via CLI na v1**: sem telas ou tabelas novas na interface web da v1. O CLI vive no backend (`uv run enade-eval ...`, com atalhos no `Makefile`), reutiliza exatamente a mesma porta `ClassificadorMultimodal` e as mesmas travas determinísticas da aplicação, e grava relatórios descartáveis (`JSON` estruturado + resumo `Markdown`) em `DATA_DIR/evals/` (fora do Git).
- **Execução 100% somente-leitura no PostgreSQL**: a `Avaliação de Classificação` lê `Questão`, `Alternativa`, `Ativo Visual`, `Taxonomia` e `Perfil de Classificação`, mas **nunca** grava `Execução de Classificação`, `Classificação` nem `Divergência de Reclassificação` no banco da aplicação.
- **Subcomandos do protocolo**:
  1. `enade-eval exportar-ouro --taxonomia <codigo> --saida evals/golden/<codigo>.json`: exporta as questões elegíveis do PostgreSQL para o snapshot versionado.
  2. `enade-eval avaliar --ouro <arquivo.json> --perfil <codigo@versao | arquivo.yaml> [--base-url ...] [--model ...] [--no-cache] [--repeticoes N]`: roda a `Avaliação de Classificação` (com cache LLM ativo por padrão; `--no-cache` para medir latência real e `--repeticoes N` para medir estabilidade em `temperature=0`, aceitando rascunhos locais de `Perfil de Classificação` e override de provedor/modelo para testar `Qwen/vLLM`).
  3. `enade-eval comparar <baseline.json> <candidato.json> [--modo-migracao]`: compara duas execuções sobre o **mesmo snapshot do `Conjunto-Ouro`**, imprime tabela de deltas + lista de **ganhos** e **regressões** questão-a-questão e retorna `exit code` determinístico (`0` aprovado / `1` regressão).
  4. `enade-eval historico [--taxonomia <codigo>]`: consulta somente-leitura sobre o PostgreSQL que mede continuamente (sem chamar LLM) a concordância histórica **IA × Humano** a partir das `Classificação`s preservadas: taxa de aprovação direta sem alteração, taxa de correção na `Disciplina` principal e taxa de correção apenas nas secundárias, agrupadas por `Perfil de Classificação` e modelo.
- **Critérios objetivos de promoção (gate híbrido, promoção sempre manual)**:
  - **Piso estrutural duro (ambos os modos)**: `conclusao_valida == 100%` e `validade_primeira_tentativa >= 95%`.
  - **Promoção de novo `Perfil de Classificação` (modo padrão)**: `acuracia_principal >= baseline`, `macro_f1_principal >= baseline - 2,0 p.p.` e `jaccard_secundarias >= baseline - 3,0 p.p.`.
  - **Migração de provedor/modelo (ex.: servidor `Qwen/vLLM`, via `--modo-migracao`)**: tolerância explícita de até `-2,0 p.p.` na `acuracia_principal` e `-5,0 p.p.` no `jaccard_secundarias` (mantendo o piso estrutural duro e a revisão humana do diff de regressões antes de alterar a configuração de produção).

### 4. Glossário e ADRs

- Formalizados os termos canônicos **`Conjunto-Ouro`** (15º termo, evitando *"gabarito de classificação"*, que colide com `Gabarito`) e **`Avaliação de Classificação`** (16º termo, distinguindo a medição offline somente-leitura da `Execução de Classificação` persistida no produto) em [GLOSSARY.md](../../../GLOSSARY.md).
- Nenhum ADR em `docs/adr/` foi aberto por se tratar de ferramental local de avaliação offline, desacoplado do banco de produção e facilmente evoluível sem impacto de migração.
