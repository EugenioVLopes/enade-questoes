# Prototipar extração em uma prova real do ENADE (Docling vs alternativa)

Type: prototype
Status: resolved
Blocked by: 01, 02

## Question

Ao rodar um protótipo descartável sobre 1 prova real + gabarito obtidos em [Obter provas e gabaritos oficiais do ENADE de Engenharia de Computação](./01-obter-provas-gabaritos-enade.md), comparando **Docling** com a melhor alternativa apontada em [Comparar ferramentas de extração de PDF para provas do ENADE (Docling vs alternativas)](./02-comparar-extracao-pdf-docling.md), qual abordagem entrega o melhor resultado ponta a ponta para:

1. Segmentar todas as questões objetivas do Componente Específico sem misturar colunas nem cortar enunciados entre páginas;
2. Preservar alternativas (A–E), tabelas, blocos de código e fórmulas;
3. Recortar e associar corretamente figuras/circuitos/gráficos à respectiva questão;
4. Extrair e parear o gabarito oficial do INEP (incluindo questões anuladas);
5. Manter tempo de execução e consumo de recursos aceitáveis na máquina local?

## Answer

### Decisão aprovada

Adotar **Docling 2.151.1 (MIT)** para extração da prova + **`pdfplumber` 0.11.10 (MIT)** para extração do gabarito oficial, descartando **PyMuPDF 2.1** (licença AGPL-3.0 e falhas graves em múltiplas colunas/alternativas) e **`CodeFormulaV2`** (muito lento em CPU e degradou blocos de código em português).

### Configuração base validada

1. **Extrator principal da prova (`Docling 2.151.1`, MIT):**
   - `PyPdfiumDocumentBackend` com `torch` CPU (`pytorch-cpu` no `uv`).
   - `do_ocr=False`, `do_table_structure=True`, `generate_picture_images=True`, `images_scale=2.0`, `do_code_enrichment=False`, `do_formula_enrichment=False`.
2. **Pós-processamento determinístico obrigatório sobre a saída do Docling:**
   - **Filtro de mídia de moldura:** descartar `PictureItem`s em margens de cabeçalho/rodapé ou abaixo de dimensões mínimas (no ENADE 2023, 65 de 80 imagens eram barcodes `*R082023XX*` e logos ENADE; 15 eram figuras/diagramas reais).
   - **Limpeza de ruído textual:** remover marcas d'água repetidas (`VALIDINEP...`), códigos de página (`*R082023XX*`) e rótulos `Área livre`.
   - **Truncamento de fim de prova:** cortar antes de `QUESTIONÁRIO DE PERCEPÇÃO` (case-insensitive, pois o INEP usa caixa mista como `PerCePÇÃo`) para evitar colisão com a renumeração `QUESTÃO 01`–`09`.
   - **Detecção automática de ToUnicode CMap corrompido (ex.: ENADE 2017):** executar detector determinístico de mojibake antes da extração padrão e, quando acionado, reprocessar com `do_ocr=True` + `RapidOcrOptions(force_full_page_ocr=True)` (já incluído com Docling).
3. **Extrator do gabarito oficial (`pdfplumber`, MIT):**
   - Extração determinística de tabela com normalização dos 3 formatos reais do INEP (`QUESTÃO DISCURSIVA N` → `***`, `ANULADA` e numeração pura `1..35`).
4. **Fallback pontual para fórmulas e símbolos (`formula-not-decoded` / fonte `Symbol`):**
   - Não usar `CodeFormulaV2` em CPU. Preservar referência à página/bbox original para permitir apoio do LLM multimodal já previsto na classificação ou correção manual na tela de revisão nos casos pontuais (ex.: alternativas em forma de sistema de equações na Q13 e resistividade `ρ` mapeada como `r` na Q10 de 2023).

### Evidências medidas no protótipo descartável

Protótipo executável em [prototypes/05-extracao-pdf/run_prototype.py](../../../prototypes/05-extracao-pdf/run_prototype.py) (com painel HTML lado a lado gerado localmente em `data/prototype-05/comparacao-extracao.html` e métricas em `data/prototype-05/summary.json`, ambos fora do Git via `.gitignore`):

| Critério | **Docling 2.151.1** (`do_ocr=False`) | **PyMuPDF 2.1** (`pymupdf-layout`) | **Docling + `CodeFormulaV2`** (5 págs) |
| --- | --- | --- | --- |
| **Tempo total (ENADE 2023, 40 págs)** | **38,0 s** (`0,95 s/pág`) | **12,0 s** (`0,30 s/pág`) | **157,3 s** (`31,5 s/pág`) |
| **Pico de RAM (RSS em subprocesso isolado)** | **2.282 MB** | **757 MB** | **2.492 MB** |
| **Segmentação CE (Q10–Q38)** | **29 / 29** | **29 / 29** | — |
| **Alternativas A–E ordenadas e separadas** | **27 / 29** *(Q13: equações; Q15: bloco C único)* | **10 / 29** *(agrupa alternativas na mesma linha)* | — |
| **Questão multipágina (Q25, p.28→p.29)** | **Intacta** (4.008 chars, Verilog+VHDL+A–E) | **Cortada** (2.827 chars, perda de código e A–C coladas) | — |
| **Figuras vetoriais/circuitos recortados** | **Nítidas** (15 figuras reais; 65 barcodes/logos filtráveis) | **Incompleto** (11 imagens em 9 questões) | Piorou texto/código em português via OCR |
| **Stress 2019 (alternativas 2 colunas Java, Q09)** | **Preservou colunas** (`A,B,C` depois `D,E`) | **Intercalou `A/D` e `B/E`** linha a linha | — |
| **Stress 2017 (corpo 2 colunas + CMap corrompido)** | Com `force_full_page_ocr=True`: **11,5 s / 2 págs**, texto limpo (`σ`, `ε`) + colunas separadas | Auto-OCR legível, mas **misturou Q09+Q10 e Q11+Q12** na mesma frase | — |
| **Gabaritos (2023 / 2019 com `ANULADA` / 2017)** | `pdfplumber`: **3/3 100% em 49–95 ms** | `pymupdf.find_tables()`: falhou em 2023 e 2019 | — |
