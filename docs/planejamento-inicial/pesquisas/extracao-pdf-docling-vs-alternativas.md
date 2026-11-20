# Comparativo de Ferramentas de Extração de PDF para Provas do ENADE

Pesquisa baseada em fontes primárias (repositórios oficiais, metadados do PyPI e documentação de API) realizada em novembro de 2026 para orientar o protótipo da decisão [05 — Prototipar extração em uma prova real do ENADE](../decisoes/05-prototipar-extracao-prova-real.md).

## Resumo Executivo

As provas do ENADE (Engenharia de Computação) distribuídas pelo INEP são tipicamente PDFs digitais nativos com **layout em duas colunas**, cabeçalhos/rodapés repetidos, **figuras/circuitos/diagramas vetoriais e raster**, tabelas (incluindo tabelas-verdade e gabaritos), blocos de código-fonte e fórmulas matemáticas.

Para execução local **sem GPU dedicada** (ambiente Python 3.13 + `uv`, como a estação atual de 28 vCPUs e 14 GiB de RAM), as duas abordagens com maior valor informativo para levar ao protótipo A/B são:

1. **Docling (`docling 2.151.1`, MIT)** — pipeline estruturado de maior fidelidade em layout, tabelas (`TableFormer`), recorte nativo de figuras com bounding boxes (`PictureItem`) e enriquecimentos opt-in de código e fórmulas (`CodeFormulaV2`), configurado com `PyPdfiumDocumentBackend` e índice `pytorch-cpu` no `uv`.
2. **PyMuPDF 2.1 (`pymupdf` + `pymupdf4llm` + `pymupdf-layout`, AGPL-3.0 / comercial)** — alternativa ultrarrápida em CPU **sem PyTorch** (usa `onnxruntime` para detecção de layout multi-coluna), com supressão nativa de cabeçalhos/rodapés, preservação de blocos de código e recorte de figuras embutidas/vetoriais (`write_images=True` / `to_json()`), sujeita a ressalva de licença (AGPL-3.0) e limitação em fórmulas matemáticas complexas.

**Papel das demais alternativas:**
- **Marker (`marker-pdf 2.2.0`)** é a **3ª opção (reserva)** caso fórmulas matemáticas em CPU exijam conversão LaTeX mais rápida que o `CodeFormulaV2` do Docling ou caso a licença AGPL-3.0 do PyMuPDF seja bloqueadora (nota: pesos dos modelos usam OpenRAIL-M modificada, livre para uso pessoal/pesquisa/startups < US$ 5M).
- **pdfplumber (`0.11.10`, MIT)** não é recomendado como extrator principal de provas de duas colunas com figuras vetoriais, mas é excelente ferramenta determinística auxiliar para extrair o **gabarito oficial em tabela** e conferir texto por coordenada.
- **Renderização (`pypdfium2`) + VLM** é **inadequado como extrator primário da prova inteira** sem GPU dedicada (alto custo/latência, não determinismo, incapacidade nativa de recortar figuras PNG limpas), mas é o **melhor fallback pontual** para transcrever recortes isolados difíceis (fórmulas escaneadas/quebradas ou diagramas com texto).

---

## Tabela Comparativa Consolidada

| Critério | Docling (`2.151.1`) | PyMuPDF (`2.1`, incl. `pymupdf4llm` + `pymupdf-layout`) | pdfplumber (`0.11.10`) | Marker (`marker-pdf 2.2.0`) | `pypdfium2` + VLM |
|---|---|---|---|---|---|
| **Duas colunas e ordem de leitura** | Nativo via detector RT-DETR (`docling-layout-heron`) + separação `body`/`furniture` | Nativo via `pymupdf-layout` (ONNX CPU) + flags `header=False`, `footer=False` | Manual (`page.crop` por coluna ou `laparams` do `pdfminer.six`); `extract_text()` linear intercala colunas | Nativo via Indra ONNX (`OrderNet` + layout) em `fast`/`no_ocr`, ou Surya 2.5 VLM em `balanced`/`vllm` | Compreende visualmente 2 colunas, mas sem determinismo garantido |
| **Recorte de figuras + bounding boxes** | **Alto**: `PictureItem` (bitmap + vetorial) com `prov/bbox` no fluxo, `generate_picture_images=True`, `ImageRefMode.REFERENCED` | **Alto**: `pymupdf-layout` marca caixas `"picture"` (bitmap + vetorial), `write_images=True` e bboxes float em `to_json()` | **Baixo**: `page.images` lista apenas XObjects bitmap e não reconstrói imagem; gráficos vetoriais viram `lines`/`curves` | **Alto**: extrai imagens de figuras (`rendered.images`), referências inline no Markdown e blocos/polígonos em JSON | **Baixo**: `pypdfium2` renderiza página inteira; VLM não gera recortes PNG exatos sem detector auxiliar |
| **Tabelas** | **Excelente** (`TableFormer` accurate/fast; 88,4% `tables_derived` no OmniParseBench) | **Bom** em grades claras (Markdown ou HTML via `table_output="html"`); menor precisão em células mescladas complexas | **Muito bom** em grades regulares (`find_tables`, `lines`/`text`); excelente para gabarito INEP | **Bom** em CPU (`fast`: 80,1% `tables_derived` via heurística + `OrderNet`); melhor só com GPU/VLM | **Muito bom** em compreensão visual, mas sujeito a truncamento e deslocamento sem dupla verificação |
| **Código-fonte** | **Muito bom** (opt-in `do_code_enrichment=True` popula `CodeItem` e `code_language`) | **Bom** (detecta fontes monoespaçadas e gera blocos de código; desativável com `ignore_code=True`) | **Fraco** (texto plano; exige heurística manual por nome de fonte) | **Bom** (isola blocos de código em Markdown) | **Muito bom** (transcreve bem código, sujeito a pequenas variações não determinísticas) |
| **Fórmulas matemáticas** | **Bom/Muito bom** (opt-in `do_formula_enrichment=True` via `CodeFormulaV2` → LaTeX; pesado em CPU) | **Fraco** (texto Unicode linear da camada do PDF; sem modelo dedicado de LaTeX) | **Fraco** (texto cru; frações/símbolos perdem estrutura 2D) | **Fraco** em `no_ocr` (49,1%); **Bom** em `fast` com `--ocr_inline_math` (77,8%); **Excelente** em `balanced` GPU (90,8%) | **Excelente** para transcrever equações em LaTeX |
| **Execução local sem GPU (CPU/RAM/modelos)** | Pesado porém viável: `torch` CPU + ~320–385 MB base (`heron` + `TableFormer`) ou ~1 GB c/ `CodeFormulaV2`; recomenda 8–16 GB RAM; ~segundos/página | **Muito leve e rápido**: sem PyTorch; wheel ~63–69 MB + `onnxruntime`; baixo uso de RAM; ~dezenas/centenas de ms por página | **Ultraleve**: 0 modelos ML (~60 KB + `pdfminer.six` + `pypdfium2`); ms/página | Misto: puxa `torch>=2.7` + 22 deps; modo `fast` usa ~18 MB ONNX (muito rápido em CPU), mas `balanced`/`vllm` sem GPU exige `llama-server` externo | Render `pypdfium2` é trivial (~3–5 MB, sem poppler), mas **VLM não roda localmente sem GPU** (exige servidor vLLM remoto ou API paga) |
| **Python 3.13 + `uv`** | Compatível (`>=3.10,<4.0`, classifiers até 3.14); configurar índice `pytorch-cpu` no `pyproject.toml` | Compatível (`>=3.11`); instalação limpa e rápida no `uv` | Compatível (`>=3.8`, classifiers até 3.14) | Compatível (`>=3.10,<4`); árvore de 22 deps (incl. `torch`, `surya-ocr`, SDKs de LLMs) | Compatível (`pypdfium2 >=3.6`) |
| **Licença** | **MIT** | **Dual: GNU AGPL-3.0 ou Comercial Artifex** | **MIT** | Código **Apache-2.0**; pesos **OpenRAIL-M modificada** (< US$ 5M receita/funding) | `pypdfium2`: **BSD-3-Clause / Apache-2.0** (+ licença/termos do provedor VLM) |

---

## Análise Detalhada por Critério

### 1. Ordem de leitura em layout de duas colunas e cabeçalhos/rodapés repetidos

- **Docling**: Executa detecção de layout por página com modelos baseados em RT-DETR (padrão `docling-layout-heron`) que rotulam cada região (`TEXT`, `SECTION_HEADER`, `TABLE`, `PICTURE`, `FORMULA`, etc.), reconstrói a ordem de leitura multi-coluna e separa explicitamente o corpo principal do documento dos elementos de moldura (`furniture`, como cabeçalhos e rodapés repetidos) no objeto Pydantic `DoclingDocument` ([Docling Model Catalog](https://github.com/docling-project/docling/blob/main/docs/usage/model_catalog.md), [DoclingDocument Concepts](https://github.com/docling-project/docling/blob/main/docs/concepts/docling_document.md)).
- **PyMuPDF 2.1 (`pymupdf` + `pymupdf4llm` + `pymupdf-layout`)**: Desde a série 2.x, o pacote `pymupdf` unificou `pymupdf-layout` e `pymupdf4llm` como dependências integradas ([PyPI `pymupdf 2.1`](https://pypi.org/pypi/pymupdf/json)), oferecendo os métodos `Document.to_markdown()`, `Document.to_json()` e `Document.to_text()` com análise de layout baseada em `onnxruntime` sem GPU ([PyMuPDF LLM & RAG](https://pymupdf.readthedocs.io/en/latest/rag.html), [PyMuPDF4LLM Docs](https://pymupdf.readthedocs.io/en/latest/pymupdf-layout/index.html)). Os parâmetros `header=False` e `footer=False` permitem descartar cabeçalhos e rodapés repetidos diretamente na exportação ([PyMuPDF Document API](https://pymupdf.readthedocs.io/en/latest/document.html)).
- **pdfplumber**: Por padrão, `page.extract_text()` ordena caracteres por `doctop` (vertical) e `x0` (horizontal), o que **mistura as duas colunas na mesma linha** em provas diagramadas em duas colunas ([pdfplumber README — Extracting text](https://github.com/jsvine/pdfplumber/blob/stable/README.md#extracting-text)). Para ler duas colunas corretamente é necessário recortar cada coluna via `page.crop((x0, y0, x1, y1))` ou ativar `laparams` do `pdfminer.six`. O agrupamento manual por coordenada `top` funciona bem para tabelas regulares de largura total, mas é frágil quando questões do ENADE misturam blocos de largura total (tabelas/figuras grandes) com enunciados em duas colunas.
- **Marker (`2.2.0`)**: Em CPU (`--mode fast` e `--mode no_ocr`), combina extração de camada de texto (`pdftext`) com os modelos ONNX in-process do `indra-ocr` (`OrderNet` + detector de layout) para ordenar colunas e descartar cabeçalhos/rodapés automaticamente ([Marker README](https://github.com/datalab-to/marker/blob/master/README.md#how-it-works)). No benchmark **OmniParseBench** (publicado pela própria Datalab — interpretar com cautela por ser benchmark do autor), `Marker fast` atingiu **86,0%** e `no_ocr` **81,4%** na suíte `olmo_multi_column`, contra **83,9%** do Docling ([Marker README — Benchmarks](https://github.com/datalab-to/marker/blob/master/README.md#benchmarks)).
- **Renderização (`pypdfium2`) + VLM**: Renderizar cada página em PNG (`dpi=200`, RGB) e enviar a um modelo de visão (ex.: servidor vLLM ou API VLM) lê bem duas colunas visualmente, mas introduz **não determinismo mesmo com `temperature=0`**, risco de completação silenciosa de texto cortado e necessidade de controlar/desligar *reasoning* (`enable_thinking: False`).

### 2. Extração e recorte de figuras/imagens vinculadas ao fluxo da questão

Em provas de Engenharia de Computação do ENADE, grande parte das figuras (circuitos digitais, máquinas de estados, diagramas UML, gráficos de funções, redes de computadores) é composta por **gráficos vetoriais PDF** ou combinações de vetor + texto, e não apenas bitmaps JPEG/PNG embutidos.

- **Docling**: Com `PdfPipelineOptions(generate_picture_images=True, images_scale=2.0)` (`scale=1.0` equivale a 72 DPI; `2.0` a 144 DPI), o detector de layout identifica a bounding box de cada figura — **seja bitmap ou diagrama vetorial** — e armazena o recorte no `PictureItem`, mantendo sua posição exata na árvore de leitura (`doc.iterate_items()`) e sua procedência (`prov` com página e bbox). A exportação suporta `element.get_image(doc).save(...)` e `doc.save_as_markdown(..., image_mode=ImageRefMode.REFERENCED)` ([Docling `export_figures.py`](https://github.com/docling-project/docling/blob/main/docs/examples/export_figures.py)).
- **PyMuPDF 2.1**: Com o módulo de layout ativo, `Document.to_markdown(write_images=True, image_path=..., image_dpi=150, image_format="png")` recorta automaticamente todas as áreas classificadas como `"picture"` (incluindo gráficos vetoriais renderizados) e injeta a referência Markdown na posição correta do texto. Em `Document.to_json()`, devolve `page_boxes` com coordenadas em ponto flutuante não arredondadas e `boxclass`, permitindo recorte customizado de alta resolução via `page.get_pixmap(clip=...)` ([PyMuPDF Document API](https://pymupdf.readthedocs.io/en/latest/document.html)).
- **pdfplumber**: A própria documentação oficial adverte que `page.images` fornece apenas coordenadas/propriedades de XObjects de imagem e **não suporta reconstruir o conteúdo da imagem diretamente** ([pdfplumber README — `image` properties](https://github.com/jsvine/pdfplumber/blob/stable/README.md#image-properties)). Para diagramas vetoriais, o usuário teria de clusterizar `lines`/`curves`/`rects` por proximidade espacial e chamar `page.crop(bbox).to_image(resolution=...)` manualmente — esforço de engenharia alto e frágil.
- **Marker (`2.2.0`)**: Extrai imagens das regiões de figura automaticamente (a menos que `--disable_image_extraction` seja usado), retornando o dicionário `images` via `text_from_rendered(rendered)` já referenciado no Markdown, além da árvore de blocos com coordenadas no modo `--output_format json` ([Marker README — Python Usage](https://github.com/datalab-to/marker/blob/master/README.md)).
- **`pypdfium2` + VLM**: `pypdfium2` renderiza apenas a página inteira (ou um recorte se as coordenadas já forem conhecidas). Um VLM genérico não entrega recortes PNG pixel-precisos das figuras da questão; dependeria de um detector de layout externo de qualquer maneira.

### 3. Qualidade em tabelas, trechos de código e fórmulas matemáticas

- **Docling**:
  - *Tabelas*: Usa **TableFormer** (`do_table_structure=True`, modos `accurate` e `fast`) ([Docling Model Catalog](https://github.com/docling-project/docling/blob/main/docs/usage/model_catalog.md)). Mesmo no benchmark publicado pela concorrente Datalab (OmniParseBench), o Docling alcançou **88,4%** em `tables_derived` (5.427 testes) e **88,1%** em `olmo_table_tests`, liderando entre os pipelines CPU locais ([Marker README — OmniParseBench per-suite](https://github.com/datalab-to/marker/blob/master/README.md)).
  - *Código e Fórmulas*: Possui enriquecimentos dedicados opt-in: `do_code_enrichment=True` (popula `CodeItem` e identifica `code_language`) e `do_formula_enrichment=True` (extrai LaTeX de blocos `FORMULA` com recorte configurável via `CodeFormulaVlmOptions.from_preset("codeformulav2", expansion_factor=..., stop_on_repetition=True)`) ([Docling Enrichments](https://github.com/docling-project/docling/blob/main/docs/usage/enrichments.md)). A documentação adverte que os enriquecimentos adicionam modelos extras e aumentam consideravelmente o tempo de processamento.
- **PyMuPDF 2.1**:
  - *Tabelas*: Converte tabelas detectadas para Markdown ou HTML (`table_output="html"`), com bom desempenho em tabelas com grade explícita (como gabaritos e tabelas-verdade), mas sem um modelo neural dedicado de estrutura de células mescladas como o TableFormer.
  - *Código*: Reconhece trechos em fonte monoespaçada e os formata automaticamente como blocos de código Markdown (controlável via `ignore_code=False`) ([PyMuPDF Document API](https://pymupdf.readthedocs.io/en/latest/document.html)).
  - *Fórmulas*: **Principal lacuna** — não conta com conversor neural de equações para LaTeX; extrai apenas glifos/Unicode da camada de texto (ou OCR opcional com Tesseract/RapidOCR), o que tende a desestruturar frações, matrizes, somatórios e integrais.
- **pdfplumber**:
  - *Tabelas*: Muito forte e auditável em tabelas de PDF nativo com linhas ou alinhamento regular (`find_tables()`, `extract_tables()`, `debug_tablefinder()`) ([pdfplumber README — Extracting tables](https://github.com/jsvine/pdfplumber/blob/stable/README.md#extracting-tables)), evitando erros de deslocamento de linha típicos de extratores lineares de texto.
  - *Código e Fórmulas*: Sem suporte semântico nativo (extração de texto bruto).
- **Marker (`2.2.0`)**:
  - *Tabelas*: No modo CPU (`fast`), obtém **80,1%** em `tables_derived` e **80,3%** em `olmo_table_tests` (bom, porém ~8 pontos abaixo do Docling) ([Marker README](https://github.com/datalab-to/marker/blob/master/README.md)).
  - *Código e Fórmulas*: Isola blocos de código. Em matemática (`olmo_arxiv_math`), o modo `no_ocr` cai para **49,1%**, enquanto `fast` (CPU ONNX com `--ocr_inline_math`) atinge **77,8%** — superando o Docling padrão sem `do_formula_enrichment` (**59,0%**), embora ainda abaixo do modo `balanced` com GPU (**90,8%**) ([Marker README](https://github.com/datalab-to/marker/blob/master/README.md)).
- **`pypdfium2` + VLM**:
  - Excelente em fórmulas LaTeX, código e tabelas visuais, mas exige validação determinística rigorosa e esquema estrito para conter truncamentos em tabelas extensas, alucinações e variações entre execuções.

### 4. Requisitos locais sem GPU dedicada, licenciamento e compatibilidade com Python 3.13 + `uv`

Dados verificados diretamente na API JSON do PyPI e nos repositórios oficiais do Hugging Face / GitHub:

- **Docling (`docling 2.151.1` → `docling-slim[standard]==2.151.1`)**:
  - *Python 3.13 + `uv`*: `requires-python: <4.0,>=3.10`, classifiers oficiais `3.10`–`3.14` ([PyPI `docling`](https://pypi.org/pypi/docling/json)). O projeto usa `uv` oficialmente ([Docling README](https://github.com/docling-project/docling/blob/main/README.md)). **Atenção no `uv`**: depende de `torch<3.0.0,>=2.2.2` e `torchvision`; em Linux sem GPU, deve-se configurar o índice explícito `https://download.pytorch.org/whl/cpu` em `pyproject.toml` (`[tool.uv.sources]`) para evitar o download de gigabytes de bibliotecas CUDA.
  - *Tamanho dos modelos (Hugging Face API)*:
    - Layout padrão (`docling-project/docling-layout-heron`): **171,8 MB** ([HF `docling-layout-heron`](https://huggingface.co/api/models/docling-project/docling-layout-heron/tree/main?recursive=true)).
    - TableFormer (`docling-project/docling-models`): **212,8 MB** (`accurate`) ou **145,5 MB** (`fast`) ([HF `docling-models`](https://huggingface.co/api/models/docling-project/docling-models/tree/main?recursive=true)).
    - Enriquecimento de código/fórmulas (`docling-project/CodeFormulaV2`): **639,8 MB** ([HF `CodeFormulaV2`](https://huggingface.co/api/models/docling-project/CodeFormulaV2/tree/main?recursive=true)).
    - Total baixado para PDF digital (`do_ocr=False`): **~320–385 MB** (sem CodeFormulaV2) ou **~1,0 GB** (com CodeFormulaV2). Pode ser pré-baixado com `docling-tools models download` para uso 100% offline ([Docling Advanced Options](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md)).
  - *CPU/RAM/Velocidade*: Em CPU moderna sem GPU (ex.: estação local de 28 vCPUs e 14 GiB RAM), recomenda-se usar `PyPdfiumDocumentBackend` (menor pico de memória por página) e desativar OCR (`do_ocr=False`) em PDFs digitais do INEP. Velocidade esperada em CPU é da ordem de segundos por página (muito mais lento se ativar `do_formula_enrichment`), perfeitamente aceitável para ingestão offline de poucas provas (~30–40 páginas cada).
  - *Licença*: **MIT**.
- **PyMuPDF (`pymupdf 2.1`, `pymupdf4llm 2.1`, `pymupdf-layout 2.1`)**:
  - *Python 3.13 + `uv`*: `requires-python: >=3.11` ([PyPI `pymupdf`](https://pypi.org/pypi/pymupdf/json)). **Não depende de PyTorch**: wheel de **63–69 MB** com apenas 9 dependências leves (`onnxruntime`, `numpy`, `networkx`, `psutil`, `pyyaml`, `tabulate`, `pymupdf-layout`, `pymupdf4llm`).
  - *CPU/RAM/Velocidade*: Muito baixo uso de RAM e execução extremamente rápida em CPU (fração de segundo por página), sem GPU nem downloads extras grandes.
  - *Licença*: **Dual Licensed — GNU AGPL-3.0 ou Artifex Commercial License** ([PyPI `pymupdf`](https://pypi.org/pypi/pymupdf/json)). Exige atenção se o aplicativo web vier a ser distribuído/hospedado comercialmente como código fechado; para uso local/estudo pessoal ou projeto aberto em AGPL-3.0, não há bloqueio.
- **pdfplumber (`0.11.10`)**:
  - *Python 3.13 + `uv`*: `requires-python: >=3.8`, classifiers `3.10`–`3.14`; apenas 3 dependências (`pdfminer.six`, `Pillow`, `pypdfium2`), wheel de **60 KB**, zero modelos de ML ([PyPI `pdfplumber`](https://pypi.org/pypi/pdfplumber/json)).
  - *Licença*: **MIT** ([pdfplumber `LICENSE.txt`](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt)).
- **Marker (`marker-pdf 2.2.0`)**:
  - *Python 3.13 + `uv`*: `requires-python: <4,>=3.10`, mas puxa **22 dependências diretas** incluindo `torch<3,>=2.7.0`, `surya-ocr`, `indra-ocr`, `scikit-learn`, `openai`, `anthropic` e `google-genai` ([PyPI `marker-pdf`](https://pypi.org/pypi/marker-pdf/json)).
  - *CPU/RAM/Velocidade*: O modo `--mode fast` (padrão em CPU) roda in-process com pesos ONNX do `indra-ocr` (~18 MB) sem servidor externo (~23,6 pg/s em benchmark concorrente da Datalab). Já os modos `balanced` e `vllm` exigem instalar o binário externo `llama-server` (`llama.cpp`) em CPU para servir o Surya 2.5 (0,69B), aumentando complexidade operacional e consumo de RAM ([Marker README — Inference backend prerequisites](https://github.com/datalab-to/marker/blob/master/README.md#inference-backend-prerequisites)).
  - *Licença*: Código **Apache-2.0**, pesos sob **AI Pubs OpenRAIL-M modificada** (uso livre para pesquisa, pessoal e startups com menos de US$ 5M de receita/investimento) ([Marker README — Commercial usage](https://github.com/datalab-to/marker/blob/master/README.md)).
- **`pypdfium2 5.15.2` + VLM**:
  - *Python 3.13 + `uv`*: `pypdfium2` tem 0 dependências externas, wheel de 2,7–5,4 MB, não exige `poppler` ([PyPI `pypdfium2`](https://pypi.org/pypi/pypdfium2/json)).
  - *Custo/latência*: Uma única página renderizada a 200 DPI consome tipicamente ~3.700–5.300 tokens de entrada e leva dezenas de segundos por página em servidor vLLM dedicado (`Qwen/Qwen3.8-27B`). Sem GPU dedicada local, exigiria API paga de VLM para cada página da prova inteira.

---

## 5. Recomendação Objetiva para o Protótipo ([Decisão 05](../decisoes/05-prototipar-extracao-prova-real.md))

Levar exatamente **2 abordagens complementares** para o protótipo descartável sobre 1 prova real + gabarito do ENADE (Engenharia de Computação):

1. **Docling (`docling` com `PyPdfiumDocumentBackend`, `do_ocr=False`, `generate_picture_images=True`, `images_scale=2.0`, `do_table_structure=True`)**
   - *Objetivo no protótipo*: Validar se entrega o pacote completo ponta a ponta em licença **MIT** — ordem de leitura em 2 colunas sem cabeçalhos/rodapés, recorte limpo de circuitos/diagramas vetoriais vinculados à questão, fidelidade em tabelas (`TableFormer`) e medição real de tempo/qualidade ao ligar `do_code_enrichment=True` e `do_formula_enrichment=True` em CPU (usando `pytorch-cpu` no `uv`).
2. **PyMuPDF 2.1 (`pymupdf` / `Document.to_markdown()` + `Document.to_json()` com `pymupdf-layout` ativo, `header=False`, `footer=False`, `write_images=True`)**
   - *Objetivo no protótipo*: Estabelecer a linha de base **sem PyTorch / baixa latência em CPU** com layout ONNX. Permite medir de forma objetiva quanto o ganho de qualidade do Docling em tabelas e fórmulas justifica o custo extra de dependências (`torch` + pesos) e tempo de processamento, além de testar se o recorte de figuras vetoriais (`"picture"`) do `pymupdf-layout` se compara ao do Docling.

### Notas táticas para o protótipo e evolução

- **Gabarito oficial do INEP**: Testar extração determinística direta com **`pdfplumber`** (ou `pymupdf` em modo tabela) — tabelas de gabarito não precisam de modelos pesados de layout.
- **Plano B para fórmulas ou bloqueio AGPL-3.0**: Se no protótipo o PyMuPDF falhar em fórmulas matemáticas **e** o Docling com `CodeFormulaV2` ficar lento demais em CPU, testar **Marker (`--mode fast --ocr_inline_math`)** como 3º candidato ou adotar um **híbrido enxuto** (Docling ou PyMuPDF para texto + recorte de figuras/fórmulas, acionando um VLM via API **apenas** nos recortes de equações ou tabelas que falharem na validação determinística).
