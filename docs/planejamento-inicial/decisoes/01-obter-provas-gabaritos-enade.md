# Obter provas e gabaritos oficiais do ENADE de Engenharia de Computação

Type: task
Status: resolved
Blocked by: none

## Question

Quais edições oficiais recentes de provas e gabaritos do ENADE de Engenharia de Computação (INEP) vamos usar como conjunto real de validação, e onde os PDFs baixados ficam armazenados localmente (fora do Git)?

## Checklist esperado

1. Identificar 2 a 3 edições oficiais de Engenharia de Computação no portal de provas e gabaritos do INEP (preferencialmente incluindo a edição mais recente disponível e ao menos uma anterior para expor variações de layout).
2. Baixar os PDFs da prova e do gabarito definitivo de cada edição para uma pasta local não versionada (ex.: `data/enade/<ano>/`).
3. Registrar na resolução: lista de arquivos baixados, URLs oficiais do INEP, quantidade de páginas, faixa numérica das questões objetivas do Componente Específico em cada edição e observações rápidas de layout (duas colunas, figuras, circuitos, tabelas, blocos de código, questões anuladas no gabarito).

## Answer

Foram obtidas **3 edições oficiais completas** do ENADE de Engenharia de Computação (**2023**, **2019** e **2017** — prova + gabarito definitivo de cada edição), armazenadas localmente em `data/enade/<ano>/` e excluídas do controle de versão via `.gitignore` (`data/`).

### Arquivos baixados e fontes oficiais do INEP

| Edição | Tipo | Arquivo local (fora do Git) | Páginas | Tamanho | Faixa objetiva CE | URL oficial de origem (INEP) |
| --- | --- | --- | ---: | ---: | --- | --- |
| **2023** | Prova | `data/enade/2023/prova_enade_2023_engenharia_computacao.pdf` | 40 | 9,8 MB | Q10–Q38 (29 questões) | `https://riep.inep.gov.br/server/api/core/bitstreams/c0f8a0e4-0ddd-4c20-9dfe-801546d5b5c5/content` (item [`20.500.14135/1447`](https://riep.inep.gov.br/handle/20.500.14135/1447)) |
| **2023** | Gabarito | `data/enade/2023/gabarito_enade_2023_engenharia_computacao.pdf` | 1 | 178 KB | Q10–Q38 (0 anuladas) | `https://riep.inep.gov.br/server/api/core/bitstreams/e9181b7b-89d6-4e45-8610-23daec2fa534/content` (item [`20.500.14135/1447`](https://riep.inep.gov.br/handle/20.500.14135/1447)) |
| **2019** | Prova | `data/enade/2019/prova_enade_2019_engenharia_computacao.pdf` | 40 | 3,0 MB | Q09–Q35 (27 questões) | `http://download.inep.gov.br/educacao_superior/enade/provas/2019/ENGENHARIA_COMPUTACAO.pdf` |
| **2019** | Gabarito | `data/enade/2019/gabarito_enade_2019_engenharia_computacao.pdf` | 1 | 93 KB | Q09–Q35 (0 anuladas no CE; Q01 de FG = `ANULADA`) | `http://download.inep.gov.br/educacao_superior/enade/gabaritos/2019/engenharia_de_computacao.pdf` |
| **2017** | Prova | `data/enade/2017/prova_enade_2017_engenharia_computacao.pdf` | 40 | 1,3 MB | Q09–Q35 (27 questões) | `http://download.inep.gov.br/educacao_superior/enade/provas/2017/13_ENG_COM_BACHAREL_BAIXA.pdf` |
| **2017** | Gabarito | `data/enade/2017/gabarito_enade_2017_engenharia_computacao.pdf` | 1 | 212 KB | Q09–Q35 (0 anuladas) | `http://download.inep.gov.br/educacao_superior/enade/gabaritos/2017/13_Engenharia_de_Computacao.pdf` |

> Nota operacional de acesso: o Repositório Institucional do INEP (`riep.inep.gov.br`) serviu a edição 2023 via HTTPS padrão; já `download.inep.gov.br` encerrou conexões TLS 1.3 no ambiente local e serviu as edições 2019 e 2017 diretamente via HTTP.

#### Checksums SHA-256

- `data/enade/2023/prova_enade_2023_engenharia_computacao.pdf`: `e9939d226a450fb55b09cc4caa7c1e44bb7f22933769bda5c0902ee8aa0021b4`
- `data/enade/2023/gabarito_enade_2023_engenharia_computacao.pdf`: `617675ef9276c7fd20c8b0285c679b766ef7ba5bd062d359917967b9a66ffd6e`
- `data/enade/2019/prova_enade_2019_engenharia_computacao.pdf`: `ad30a6586d0ec844ce0cbd4159b59c5544c18c540dd73625cccd6f02f88f66de`
- `data/enade/2019/gabarito_enade_2019_engenharia_computacao.pdf`: `0c2caa1e804ae9fcb9db7813fc251c97c82e502e225f21181b8ff93a4aa47127`
- `data/enade/2017/prova_enade_2017_engenharia_computacao.pdf`: `25d070cf2b40264c74df05e1550b670711f67a242a47e6415cbe6d2088aa55c2`
- `data/enade/2017/gabarito_enade_2017_engenharia_computacao.pdf`: `234e58522f4f8bf5e9ec22754db6f5d2e5e9f09398f990c2f01016e07cf7293b`

### Observações de layout relevantes para o protótipo de extração

1. **Figuras, circuitos e diagramas são majoritariamente vetoriais**: apesar de cada caderno de 40 páginas conter diversas figuras, circuitos elétricos/digitais, grafos, autômatos e gráficos (ex.: 2023 Q10, Q11, Q13, Q22–Q25, Q31; 2019 Q16–Q19, Q23–Q24, Q26–Q29, Q31–Q32), `pdfimages -list` detecta apenas **3 a 5 imagens raster embutidas por prova**. Extração ingênua de imagens embutidas perderia quase todas as figuras; o pipeline precisará de detecção de regiões de layout + recorte renderizado da página.
2. **Variação real de colunas entre edições**:
   - **2023**: enunciados e alternativas predominantemente em **1 coluna** (com até 2 questões por página, ex.: p.22, p.30, p.34, p.37–38).
   - **2019**: enunciados em **1 coluna**, mas várias questões dispõem as **alternativas em 2 colunas lado a lado** (ex.: Q09 com blocos de código Java em `A/D`, `B/E`).
   - **2017**: **layout em 2 colunas no corpo das questões** no Componente Específico (ex.: Q09 e Q10 lado a lado na p.17).
3. **Encoding corrompido (ToUnicode CMap) em 2017**: gerado por `Adobe Acrobat 7.0 / Acrobat Distiller 7.0`, o PDF de 2017 produz ~43,6% de caracteres mojibake em `pdftotext` (ex.: `sĞƌŝĮƋƵĞ` em vez de `Verifique`), provando a necessidade de detecção automática de texto corrompido + fallback de OCR/visão para edições antigas.
4. **Símbolos e blocos de código**:
   - Símbolos matemáticos/gregos em fonte `Symbol` sofrem mapeamento enganoso em texto puro (ex.: resistividade `ρ` extraída como `r` na Q10 de 2023).
   - Blocos de código (Java, C, pseudocódigo, SQL/tabelas) aparecem tanto em enunciados quanto em alternativas (2023 Q15, Q16, Q22; 2019 Q09, Q20, Q21, Q25, Q30).
5. **Ruído de página e armadilha de segmentação**:
   - Marcas d'água e cabeçalhos repetidos: `VALIDINEP2023...` e `*R082023XX*` (2023), `*R092019XX*` e blocos `ÁREA LIVRE` (2019), `*R132017XX*` (2017).
   - **Questionário de Percepção da Prova** no final de 2023 (p.39, em 2 colunas) reutiliza os rótulos `QUESTÃO 01` a `QUESTÃO 09`; o segmentador deve truncar antes dessa seção para não colidir com as questões reais.
6. **Três formatos distintos de tabela de gabarito**:
   - **2023**: inclui linhas `QUESTÃO DISCURSIVA 1` e `QUESTÃO DISCURSIVA 2` com valor `***`, além de `QUESTÃO 1`..`QUESTÃO 38`.
   - **2019**: apenas objetivas (`QUESTÃO 1`..`QUESTÃO 35`), contendo o valor literal `ANULADA` (Q01) — útil para validar o estado de questão anulada no parser.
   - **2017**: apenas números puros (`1`..`35`) sem o prefixo `QUESTÃO`.
