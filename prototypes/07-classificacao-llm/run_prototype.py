#!/usr/bin/env python3
"""PROTOTYPE (descartável) — Ticket 07: Classificação multimodal, perfis versionados e validação.

Executa classificação estruturada sobre 14 questões reais do ENADE 2023 (saída do Docling do
protótipo 05) e gera um painel HTML autossuficiente em data/prototype-07/relatorio-classificacao.html.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import APIStatusError, OpenAI
from PIL import Image
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parents[2]
DOCLING_2023_MD = ROOT / "data" / "prototype-05" / "docling_2023" / "output.md"
GABARITOS_JSON = ROOT / "data" / "prototype-05" / "gabaritos.json"
OUT_DIR = ROOT / "data" / "prototype-07"
CACHE_DIR = OUT_DIR / "cache"

# 14 questões reais do ENADE 2023 CE escolhidas para cobrir:
# - Todas as 7 questões com Ativo Visual real (Q10, Q13, Q22, Q23, Q24, Q25, Q32)
# - Alertas de extração reais (Q10 símbolo ρ->r, Q13 formula-not-decoded, Q15 bloco C único)
# - Principais fronteiras interdisciplinares e cenários distratores (Q11, Q12, Q16, Q28, Q33, Q35)
SAMPLE_NUMBERS = [10, 11, 12, 13, 15, 16, 22, 23, 24, 25, 28, 32, 33, 35]
SAMPLE_NUMBERS_FREE = [10, 11, 12, 13, 15, 22, 23, 24, 28, 33]
ABLATION_IMAGE_NUMBERS = [13, 23, 24]
ABLATION_IMAGE_NUMBERS_FREE = [13, 23]
STABILITY_NUMBERS = [11, 23, 28]
STABILITY_NUMBERS_FREE = [11, 28]

# ---------------------------------------------------------------------------
# 1. Modelos de Domínio (espelhando GLOSSARY.md / Ticket 06)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DisciplinaDef:
    codigo: str
    nome: str
    ementa: str
    ativa: bool = True


@dataclass(frozen=True)
class TaxonomiaDef:
    codigo: str
    nome: str
    curso_referencia: str
    disciplinas: tuple[DisciplinaDef, ...]

    def ativas(self) -> list[DisciplinaDef]:
        return [d for d in self.disciplinas if d.ativa]

    def mapa_ativas(self) -> dict[str, DisciplinaDef]:
        return {d.codigo: d for d in self.disciplinas if d.ativa}

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "disciplinas": [
                {"codigo": d.codigo, "nome": d.nome, "ementa": d.ementa, "ativa": d.ativa}
                for d in self.disciplinas
            ],
        }


@dataclass(frozen=True)
class PerfilClassificacaoDef:
    codigo: str
    versao: str
    descricao: str
    diretrizes_gerais: str
    guia_fronteiras: str = ""

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "versao": self.versao,
            "diretrizes_gerais": self.diretrizes_gerais,
            "guia_fronteiras": self.guia_fronteiras,
        }


@dataclass
class QuestaoExtraida:
    numero: int
    enunciado_md: str
    alternativas: dict[str, str]
    ativos_visuais: list[Path]
    gabarito: str
    alertas_extracao: list[str] = field(default_factory=list)
    nota_amostra: str = ""


# ---------------------------------------------------------------------------
# 2. Taxonomias e Perfis Versionados
# ---------------------------------------------------------------------------

TAXONOMIA_ENADE_V1 = TaxonomiaDef(
    codigo="enade-ec-v1",
    nome="Matriz ENADE / DCNs — Engenharia de Computação (18 disciplinas)",
    curso_referencia="Engenharia de Computação",
    disciplinas=(
        DisciplinaDef(
            "matematica-e-estatistica",
            "Matemática, Probabilidade e Estatística",
            "Cálculo diferencial/integral, equações diferenciais, álgebra linear, cálculo numérico, probabilidade, variáveis aleatórias, inferência e estatística aplicada.",
        ),
        DisciplinaDef(
            "fisica-e-materiais",
            "Física e Ciência dos Materiais",
            "Mecânica, eletromagnetismo, ondas/óptica, termodinâmica básica, propriedades elétricas/semicondutoras de materiais e fundamentos físicos de Engenharia.",
        ),
        DisciplinaDef(
            "matematica-discreta-e-grafos",
            "Matemática Discreta, Lógica e Teoria dos Grafos",
            "Lógica proposicional e de predicados, conjuntos, relações, indução, combinatória, recorrências, teoria dos números e teoria dos grafos (caminhos, árvores, conectividade, coloração).",
        ),
        DisciplinaDef(
            "pesquisa-operacional-e-otimizacao",
            "Pesquisa Operacional e Otimização",
            "Programação linear (modelagem, Simplex, dualidade), programação inteira, otimização combinatória, fluxos em redes, teoria de filas e simulação de eventos discretos.",
        ),
        DisciplinaDef(
            "algoritmos-e-estruturas-de-dados",
            "Algoritmos, Programação e Estruturas de Dados",
            "Paradigmas e fundamentos de programação (estruturada, OO, funcional), estruturas lineares/árvores/hashing/heaps, ordenação, busca, projeto e análise de complexidade de algoritmos (divisão e conquista, guloso, programação dinâmica).",
        ),
        DisciplinaDef(
            "linguagens-formais-e-compiladores",
            "Linguagens Formais, Autômatos e Compiladores",
            "Hierarquia de Chomsky, expressões regulares, autômatos finitos e de pilha, gramáticas livres de contexto, máquinas de Turing, decidibilidade/computabilidade e fases de compilação.",
        ),
        DisciplinaDef(
            "engenharia-de-software-e-ihc",
            "Engenharia de Software e Interação Humano-Computador",
            "Processos e ciclo de vida (ágeis e tradicionais), engenharia de requisitos, modelagem (UML), arquitetura e padrões de projeto, qualidade, verificação/validação/testes, manutenção, usabilidade, acessibilidade e avaliação de IHC.",
        ),
        DisciplinaDef(
            "banco-de-dados",
            "Banco de Dados",
            "Modelagem conceitual (MER/EER), modelo relacional, álgebra relacional, SQL, normalização, indexação, processamento de consultas, transações (ACID), controle de concorrência, recuperação e bancos NoSQL.",
        ),
        DisciplinaDef(
            "circuitos-e-eletronica",
            "Circuitos Elétricos e Eletrônica",
            "Leis de Kirchhoff, análise nodal/malhas, teoremas (Thévenin/Norton), circuitos RC/RL/RLC (DC/AC, fasores), diodos, transistores (BJT/MOSFET), amplificadores operacionais, fontes e condicionamento analógico de sinais.",
        ),
        DisciplinaDef(
            "sistemas-digitais-e-embarcados",
            "Sistemas Digitais e Sistemas Embarcados",
            "Álgebra booleana, simplificação (Karnaugh), circuitos combinacionais e sequenciais (flip-flops, contadores, FSMs), VHDL/Verilog/FPGA, microcontroladores, interfaces/periféricos (GPIO, PWM, ADC/DAC, UART/SPI/I2C), firmware e sistemas de tempo real.",
        ),
        DisciplinaDef(
            "arquitetura-de-computadores",
            "Organização e Arquitetura de Computadores",
            "Representação de dados e aritmética computacional, conjunto de instruções (ISA), caminho de dados e controle, pipeline e hazards, hierarquia de memória (cache), E/S, DMA, arquiteturas superescalares, multicore e avaliação de desempenho (CPI, lei de Amdahl).",
        ),
        DisciplinaDef(
            "sistemas-operacionais",
            "Sistemas Operacionais",
            "Processos e threads, escalonamento de CPU (incluindo tempo real), sincronização e concorrência (semáforos, mutex, deadlock), gerência de memória (paginação, segmentação, memória virtual), sistemas de arquivos, gerência de E/S e virtualização.",
        ),
        DisciplinaDef(
            "redes-e-comunicacoes",
            "Redes de Computadores e Sistemas de Comunicação",
            "Camada física e princípios de telecomunicações (modulação, multiplexação, meios de transmissão), modelos OSI e TCP/IP, enlace/Ethernet/Wi-Fi, roteamento e endereçamento IP (CIDR/sub-redes), transporte (TCP/UDP, controle de congestionamento) e protocolos de aplicação (DNS, HTTP).",
        ),
        DisciplinaDef(
            "sistemas-distribuidos-e-paralelos",
            "Sistemas Distribuídos e Processamento Paralelo",
            "Arquiteturas paralelas (memória compartilhada/distribuída, OpenMP, MPI, GPU), comunicação entre processos (RPC, REST, mensageria), relógios lógicos, coordenação/consenso, tolerância a falhas, replicação, consistência e computação em nuvem.",
        ),
        DisciplinaDef(
            "seguranca-computacional",
            "Segurança de Sistemas de Computação",
            "Tríade CIA, criptografia simétrica e assimétrica, hashes, assinatura digital e PKI/certificados, autenticação e controle de acesso, segurança de redes (TLS, firewall, IDS/VPN), vulnerabilidades de software/web e gestão de riscos/normas (LGPD, ISO 27001).",
        ),
        DisciplinaDef(
            "ia-e-ciencia-de-dados",
            "Inteligência Artificial e Ciência de Dados",
            "Busca heurística, representação de conhecimento, aprendizado de máquina (supervisionado, não supervisionado, redes neurais), avaliação de modelos, ciência de dados (coleta, limpeza, análise exploratória, mineração e visualização de dados).",
        ),
        DisciplinaDef(
            "sinais-controle-e-automacao",
            "Processamento de Sinais, Controle e Automação",
            "Sinais e sistemas lineares invariantes no tempo, séries/transformadas de Fourier, Laplace e Z, teorema da amostragem, filtros digitais/DSP, modelagem de sistemas dinâmicos, função de transferência, estabilidade, controladores (PID), automação industrial (CLPs, sensores/atuadores, SCADA).",
        ),
        DisciplinaDef(
            "gestao-viabilidade-e-etica",
            "Gestão de Projetos, Viabilidade Técnico-Econômica e Ética Profissional",
            "Gestão de projetos e ciclo de vida, estudos de viabilidade técnica/social/econômica (engenharia econômica: VPL, TIR, payback), administração/empreendedorismo, metodologia científica, propriedade intelectual, legislação profissional, ética e sustentabilidade ambiental.",
        ),
    ),
)

TAXONOMIA_PPC_ENXUTO = TaxonomiaDef(
    codigo="ppc-enxuto-v1",
    nome="PPC Universitário Simulado — Núcleos Integrados (9 disciplinas)",
    curso_referencia="Engenharia de Computação (PPC Exemplo)",
    disciplinas=(
        DisciplinaDef("ppc-fundamentos-mat-fis", "Fundamentos de Matemática e Física", "Cálculo, estatística, física aplicada, materiais, lógica, matemática discreta, grafos e otimização."),
        DisciplinaDef("ppc-programacao-ed", "Programação, Algoritmos e Estruturas de Dados", "Linguagens de programação, alocação de memória em C, estruturas de dados, complexidade e paradigmas."),
        DisciplinaDef("ppc-teoria-compiladores", "Teoria da Computação e Compiladores", "Linguagens formais, autômatos, gramáticas e construção de compiladores."),
        DisciplinaDef("ppc-es-bd", "Engenharia de Software, IHC e Bancos de Dados", "Requisitos, arquitetura de software, testes, usabilidade/acessibilidade, modelagem relacional e SQL."),
        DisciplinaDef("ppc-eletronica-analogica", "Circuitos Elétricos e Eletrônica Analógica", "Análise de circuitos, Kirchhoff, resistores, filtros analógicos, AmpOp, diodos e transistores."),
        DisciplinaDef("ppc-hardware-embarcados", "Sistemas Digitais, Embarcados e Arquitetura", "Circuitos digitais, HDL (VHDL/Verilog), microcontroladores, GPIO, arquitetura de computadores e desempenho."),
        DisciplinaDef("ppc-so-paralelo", "Sistemas Operacionais e Concorrência", "Processos, threads, escalonamento, paginação/memória virtual, virtualização e programação paralela."),
        DisciplinaDef("ppc-redes-dist-seg", "Redes, Sistemas Distribuídos e Segurança", "Protocolos OSI/TCP/IP, roteamento, sockets, nuvem, microsserviços e segurança computacional."),
        DisciplinaDef("ppc-ia-controle-sinais", "IA, Ciência de Dados, Sinais e Controle", "Busca heurística, aprendizado de máquina, processamento de sinais, amostragem, PID e automação."),
    ),
)

GUIA_FRONTEIRAS_ENADE = """
GUIA EDITORIAL DE DESAMBIGUAÇÃO DE FRONTEIRAS (siga rigorosamente ao escolher disciplina_principal vs disciplinas_secundarias):
1. Arquitetura de Computadores × Sistemas Operacionais:
   - Foco em hardware, endereçamento físico/cache, pipeline ou métricas de CPU (CPI/miss rate) -> arquitetura-de-computadores.
   - Foco em políticas de escalonamento, tabelas de páginas, troca de contexto (MMU/TLB na troca de processos) ou sincronização do kernel -> sistemas-operacionais.
2. Circuitos Elétricos e Eletrônica × Sistemas Digitais e Embarcados:
   - Exige análise de tensões, correntes, resistência/resistividade em circuito, ganho ou resposta analógica (ex.: AmpOp, RC) -> circuitos-e-eletronica.
   - Exige lógica booleana, registradores de direção/I/O (GPIO), temporização digital, flip-flops, VHDL/Verilog ou firmware/manipulação bitwise de registradores -> sistemas-digitais-e-embarcados.
3. Circuitos e Eletrônica × Sinais, Controle e Automação:
   - Cálculo/análise de topologia de circuitos com AmpOp, impedância de entrada ou componentes elétricos (mesmo sendo filtros analógicos RC/AmpOp) -> circuitos-e-eletronica (com sinais-controle-e-automacao como secundária se envolver resposta em frequência/corte).
   - Análise abstrata de resposta em frequência, transformadas, teorema da amostragem, malha de controle ou controlador PID -> sinais-controle-e-automacao.
4. Sistemas Digitais e Embarcados × Algoritmos e Estruturas de Dados:
   - Se o código em C exige rastreio algorítmico/operações de linguagem ou gerenciamento de memória (malloc/free) -> algoritmos-e-estruturas-de-dados (com sistemas-digitais-e-embarcados ou sistemas-operacionais como secundária quando aplicável).
   - Se o foco avaliado é o hardware embarcado, pinos, registradores ou HDL -> sistemas-digitais-e-embarcados.
5. Redes e Comunicações × Sistemas Distribuídos e Paralelos:
   - Camadas OSI/TCP-IP, roteamento (OSPF), sub-redes ou comparação estrutural TCP vs UDP -> redes-e-comunicacoes (mesmo que o enunciado cite sistemas distribuídos como contexto de uso; neste caso sistemas-distribuidos-e-paralelos entra como secundária).
   - Coordenação, consenso, consistência, nuvem, microsserviços ou paralelismo -> sistemas-distribuidos-e-paralelos.
6. Algoritmos e ED × Matemática Discreta e Grafos:
   - Propriedades formais de relações (reflexividade, simetria, transitividade, classes de equivalência), lógica ou provas em grafos -> matematica-discreta-e-grafos.
   - Implementação, estruturas de dados (pilha/fila/vetor) ou análise de complexidade -> algoritmos-e-estruturas-de-dados.
7. Inteligência Artificial e Ciência de Dados × Algoritmos e ED / Grafos:
   - Busca heurística (busca gulosa usando função heurística de distância até o objetivo, A*) ou modelos de ML (SVM, redes neurais) -> ia-e-ciencia-de-dados (com algoritmos-e-estruturas-de-dados ou matematica-discreta-e-grafos como secundária).
8. Regra anti-distrator de contexto:
   - Questões do ENADE frequentemente usam um cenário prático como pano de fundo (ex.: "em um cluster computacional..." para cobrar relação de equivalência, ou "controlador PID..." para cobrar adequação de fila/pilha). Classifique como `disciplina_principal` o CONHECIMENTO TÉCNICO EFETIVAMENTE EXIGIDO PARA RESOLVER AS ALTERNATIVAS, e use `disciplinas_secundarias` para o domínio secundário realmente cobrado (nunca para mero enfeite textual).
""".strip()

PERFIL_V1_EMENTAS = PerfilClassificacaoDef(
    codigo="enade-padrao",
    versao="v1-ementas",
    descricao="Prompt base apenas com catálogo de disciplinas e ementas resumidas",
    diretrizes_gerais=(
        "Você é um especialista acadêmico em Engenharia de Computação encarregado de classificar "
        "questões objetivas do ENADE segundo a Taxonomia fornecida.\n"
        "Analise integralmente o enunciado, todas as alternativas e todas as imagens anexadas (se houver).\n"
        "Escolha EXATAMENTE 1 `disciplina_principal` entre os códigos ativos da Taxonomia e de 0 a 2 "
        "`disciplinas_secundarias` (somente se a questão realmente cobrar conteúdo substancial da disciplina secundária).\n"
        "Gere de 1 a 4 `topicos` curtos em kebab-case sem acentos (ex.: 'memoria-virtual', 'filtro-passa-baixa').\n"
        "Forneça uma `justificativa` técnica concisa (2 a 4 frases) citando evidências concretas do enunciado/imagem.\n"
        "Informe `confianca` entre 0.0 e 1.0 (use < 0.70 quando houver ambiguidade forte ou informação ilegível/incompleta)."
    ),
)

PERFIL_V2_FRONTEIRAS = PerfilClassificacaoDef(
    codigo="enade-padrao",
    versao="v2-fronteiras",
    descricao="Prompt com ementas + guia editorial de 14 fronteiras + regra anti-distrator",
    diretrizes_gerais=PERFIL_V1_EMENTAS.diretrizes_gerais,
    guia_fronteiras=GUIA_FRONTEIRAS_ENADE,
)

PERFIL_PPC_V1 = PerfilClassificacaoDef(
    codigo="ppc-enxuto",
    versao="v1-ppc",
    descricao="Classificação sob segunda Taxonomia (PPC universitário de 9 núcleos)",
    diretrizes_gerais=(
        "Você é um coordenador de curso classificando questões do ENADE para o banco interno de um "
        "PPC universitário específico.\n"
        "Analise o enunciado, alternativas e imagens anexadas. Escolha EXATAMENTE 1 `disciplina_principal` "
        "e de 0 a 2 `disciplinas_secundarias` exclusivamente entre os códigos listados na Taxonomia do PPC.\n"
        "Priorize o conhecimento efetivamente exigido para responder a questão (ignore cenários meramente ilustrativos)."
    ),
)

# ---------------------------------------------------------------------------
# 3. Parsing da Amostra Real do ENADE 2023 (saída Docling do Protótipo 05)
# ---------------------------------------------------------------------------

NOTAS_AMOSTRA: dict[int, str] = {
    10: "Imagem (resistor cilíndrico) + tabela + símbolo ρ→r (Fronteira Circuitos × Física/Materiais)",
    11: "Texto puro — OSPF + Dijkstra (Fronteira Redes × Algoritmos/Grafos)",
    12: "Tabela — Relações de equivalência com cenário distrator de cluster",
    13: "Imagem essencial (circuito + grafo) + formula-not-decoded nas alternativas",
    15: "Código C — Memory leak malloc/free + alternativas agrupadas em bloco único",
    16: "Código C — Operações bitwise com contexto de sistemas embarcados",
    22: "Imagem essencial (diagrama relacional de 3 tabelas) + consultas SQL",
    23: "Imagem essencial (2 circuitos de filtros com AmpOp — fronteira Circuitos × Sinais)",
    24: "Imagem essencial (esquema elétrico de porta paralela embarcada GPIO)",
    25: "Imagem essencial (contador 4 bits flip-flops JK) + código Verilog e VHDL multipágina",
    28: "Texto puro — Paginação + MMU + TLB (Fronteira clássica SO × Arquitetura)",
    32: "Imagem essencial (grafo de cidades do Brasil) + tabela — Busca gulosa (IA × Algoritmos)",
    33: "Texto puro — Controlador PID + estruturas fila/pilha (Fronteira Controle × ED)",
    35: "Texto puro — TCP vs UDP em sistemas distribuídos (Fronteira Redes × Distribuídos)",
}


def is_real_content_image(img_path: Path) -> bool:
    """Filtra barcodes/logos de margem do INEP usando dimensões mínimas medidas no protótipo 05."""
    if not img_path.exists():
        return False
    try:
        with Image.open(img_path) as im:
            w, h = im.size
        # Figuras reais do CE têm >= 400x200 px; barcodes/logos de página ficam abaixo disso
        return w >= 350 and h >= 180
    except Exception:
        return False


def carregar_gabarito_2023() -> dict[int, str]:
    raw = json.loads(GABARITOS_JSON.read_text(encoding="utf-8"))
    items = raw["2023"]["pdfplumber"]["items"]
    return {it["numero"]: it["gabarito"] for it in items if it["tipo"] == "objetiva"}


def carregar_questoes_2023(numeros: list[int]) -> list[QuestaoExtraida]:
    md = DOCLING_2023_MD.read_text(encoding="utf-8")
    # 1. Cortar antes do Questionário de Percepção (case-insensitive)
    m_end = re.search(r"##\s*QUEST[IÍ]ON[AÁ]R[IÍ]O\s+DE\s+PERCEP", md, re.I)
    if m_end:
        md = md[: m_end.start()]

    # 2. Localizar início do Componente Específico (QUESTÃO 10 em diante)
    m_start = re.search(r"^##\s*QUESTÃO\s+10\b", md, re.M)
    if not m_start:
        raise RuntimeError("Não foi possível localizar QUESTÃO 10 no output.md do Docling.")
    ce_md = md[m_start.start() :]

    # 3. Dividir por cabeçalho ## QUESTÃO NN
    parts = re.split(r"(?m)^##\s*QUESTÃO\s+(\d+)\s*$", ce_md)
    gabarito_map = carregar_gabarito_2023()

    questoes_por_num: dict[int, QuestaoExtraida] = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1]
        if num not in numeros:
            continue

        # Limpeza determinística de ruído do INEP
        body = re.sub(r"VALIDIN[E3]?[EP]*2023[A-Z0-9]*", "", body)
        body = re.sub(r"<!--\s*PAGE_BREAK\s*-->", "", body)

        # Coletar imagens reais referenciadas e remover referências de barcodes/logos
        ativos: list[Path] = []
        def _replace_img(match: re.Match[str]) -> str:
            p = Path(match.group(1).strip())
            if is_real_content_image(p):
                if p not in ativos:
                    ativos.append(p)
                idx = ativos.index(p) + 1
                return f"[FIGURA {idx} ANEXADA]"
            return ""

        body_clean = re.sub(r"!\[Image\]\(([^)]+)\)", _replace_img, body)
        body_clean = re.sub(r"\n{3,}", "\n\n", body_clean).strip()

        # Alertas de extração determinísticos
        alertas: list[str] = []
        if "<!-- formula-not-decoded -->" in body_clean:
            alertas.append("formula_nao_decodificada")
        if num == 10 and "resistividade r" in body_clean:
            alertas.append("simbolo_fonte_symbol_corrompido")

        # Extrair alternativas A..E quando listadas como `- A ...`
        alternativas: dict[str, str] = {}
        alt_matches = list(re.finditer(r"(?m)^-\s+([A-E])\s+(.*)$", body_clean))
        enunciado_md = body_clean
        if len(alt_matches) >= 5:
            # Pegar o bloco das 5 alternativas finais (A..E)
            first_alt_pos = alt_matches[0].start()
            enunciado_md = body_clean[:first_alt_pos].strip()
            for idx_m, m in enumerate(alt_matches):
                letra = m.group(1)
                start_txt = m.start(2)
                end_txt = alt_matches[idx_m + 1].start() if idx_m + 1 < len(alt_matches) else len(body_clean)
                alternativas[letra] = body_clean[start_txt:end_txt].strip()
        else:
            alertas.append("alternativas_incompletas")

        questoes_por_num[num] = QuestaoExtraida(
            numero=num,
            enunciado_md=enunciado_md,
            alternativas=alternativas,
            ativos_visuais=ativos,
            gabarito=gabarito_map.get(num, "?"),
            alertas_extracao=alertas,
            nota_amostra=NOTAS_AMOSTRA.get(num, ""),
        )

    return [questoes_por_num[n] for n in numeros if n in questoes_por_num]


# ---------------------------------------------------------------------------
# 4. Contrato Estruturado, Travas Determinísticas e Porta ClassificadorMultimodal
# ---------------------------------------------------------------------------


class SaidaBrutaLLM(BaseModel):
    disciplina_principal: str = Field(..., description="Código slug exato da disciplina principal.")
    disciplinas_secundarias: list[str] = Field(
        default_factory=list,
        description="De 0 a 2 códigos slug exatos de disciplinas secundárias (sem repetir a principal).",
    )
    topicos: list[str] = Field(
        default_factory=list,
        description="De 1 a 4 tópicos curtos em kebab-case sem acentos.",
    )
    justificativa: str = Field(..., min_length=10, description="Justificativa técnica concisa em português.")
    confianca: float = Field(..., ge=0.0, le=1.0, description="Grau de confiança entre 0.0 e 1.0.")


@dataclass
class ClassificacaoValidada:
    disciplina_principal: str
    disciplinas_secundarias: list[str]
    topicos: list[str]
    justificativa: str
    confianca: float
    alertas_validacao: list[str]
    requer_revisao_prioritaria: bool


def normalizar_topico(raw: str) -> str:
    txt = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9]+", "-", txt).strip("-")
    return txt[:48]


def validar_e_normalizar_classificacao(
    bruta: SaidaBrutaLLM,
    taxonomia: TaxonomiaDef,
    alertas_extracao: list[str],
) -> tuple[ClassificacaoValidada | None, str | None]:
    """Travas determinísticas pós-LLM.

    Retorna (ClassificacaoValidada, None) se válida (mesmo com saneamento leve),
    ou (None, motivo_erro) se a disciplina principal estiver fora do catálogo (aciona retry).
    """
    ativos = taxonomia.mapa_ativas()
    alertas: list[str] = []

    principal = bruta.disciplina_principal.strip()
    if principal not in ativos:
        return None, f"disciplina_principal '{principal}' não pertence ao catálogo ativo de '{taxonomia.codigo}'"

    sec_limpas: list[str] = []
    for raw_sec in bruta.disciplinas_secundarias:
        sec = raw_sec.strip()
        if sec == principal:
            alertas.append(f"removida_secundaria_igual_principal:{sec}")
            continue
        if sec not in ativos:
            alertas.append(f"removida_secundaria_invalida:{sec}")
            continue
        if sec in sec_limpas:
            alertas.append(f"removida_secundaria_duplicada:{sec}")
            continue
        sec_limpas.append(sec)

    if len(sec_limpas) > 2:
        alertas.append(f"secundarias_truncadas_para_2:{len(sec_limpas)}")
        sec_limpas = sec_limpas[:2]

    topicos_limpos: list[str] = []
    for t in bruta.topicos:
        norm = normalizar_topico(t)
        if norm and norm not in topicos_limpos:
            topicos_limpos.append(norm)
    if len(topicos_limpos) > 4:
        topicos_limpos = topicos_limpos[:4]

    confianca = round(max(0.0, min(1.0, float(bruta.confianca))), 3)
    if confianca < 0.70:
        alertas.append("baixa_confianca")

    requer_prioridade = bool(
        confianca < 0.70
        or any(a in {"formula_nao_decodificada", "alternativas_incompletas"} for a in alertas_extracao)
        or any(a.startswith("removida_secundaria_invalida") for a in alertas)
    )

    return (
        ClassificacaoValidada(
            disciplina_principal=principal,
            disciplinas_secundarias=sec_limpas,
            topicos=topicos_limpos,
            justificativa=bruta.justificativa.strip(),
            confianca=confianca,
            alertas_validacao=alertas,
            requer_revisao_prioritaria=requer_prioridade,
        ),
        None,
    )


def construir_json_schema_plano(taxonomia: TaxonomiaDef) -> dict[str, Any]:
    """Gera JSON Schema plano (sem $defs/$ref nem title) compatível com Gemini, OpenAI e vLLM."""
    codigos = [d.codigo for d in taxonomia.ativas()]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "disciplina_principal",
            "disciplinas_secundarias",
            "topicos",
            "justificativa",
            "confianca",
        ],
        "properties": {
            "disciplina_principal": {
                "type": "string",
                "enum": codigos,
                "description": "Código slug exato da disciplina principal.",
            },
            "disciplinas_secundarias": {
                "type": "array",
                "items": {"type": "string", "enum": codigos},
                "maxItems": 2,
                "description": "De 0 a 2 códigos de disciplinas secundárias (não repetir a principal).",
            },
            "topicos": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
                "description": "De 1 a 4 tópicos curtos em kebab-case sem acentos.",
            },
            "justificativa": {
                "type": "string",
                "description": "Justificativa técnica concisa em português (2 a 4 frases).",
            },
            "confianca": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Grau de confiança entre 0.0 e 1.0.",
            },
        },
    }


def montar_prompts(
    questao: QuestaoExtraida,
    taxonomia: TaxonomiaDef,
    perfil: PerfilClassificacaoDef,
    enviar_imagens: bool,
) -> tuple[str, str]:
    catalogo_linhas = [
        f"- `{d.codigo}` ({d.nome}): {d.ementa}"
        for d in taxonomia.ativas()
    ]
    system_parts = [
        perfil.diretrizes_gerais,
        "",
        f"TAXONOMIA ATIVA: {taxonomia.nome} (`{taxonomia.codigo}`)",
        "CATÁLOGO FECHADO DE DISCIPLINAS PERMITIDAS (use SOMENTE estes códigos):",
        "\n".join(catalogo_linhas),
    ]
    if perfil.guia_fronteiras:
        system_parts.extend(["", perfil.guia_fronteiras])
    system_prompt = "\n".join(system_parts)

    user_parts = [
        f"QUESTÃO {questao.numero:02d} (ENADE 2023 — Engenharia de Computação — Componente Específico)",
    ]
    if questao.alertas_extracao:
        user_parts.append(f"Alertas de extração do PDF: {', '.join(questao.alertas_extracao)}")
    user_parts.extend(["", "ENUNCIADO:", questao.enunciado_md])
    if questao.alternativas:
        user_parts.append("\nALTERNATIVAS:")
        for letra in ["A", "B", "C", "D", "E"]:
            if letra in questao.alternativas:
                user_parts.append(f"{letra}) {questao.alternativas[letra]}")
    if questao.ativos_visuais and not enviar_imagens:
        user_parts.append("\n[NOTA: imagens da questão foram omitidas propositalmente neste teste de ablação.]")
    elif questao.ativos_visuais:
        user_parts.append(f"\n[{len(questao.ativos_visuais)} imagem(ns) da questão anexada(s) abaixo — considere-as integralmente na análise.]")

    user_prompt = "\n".join(user_parts)
    return system_prompt, user_prompt


@dataclass
class ResultadoChamada:
    dados_brutos: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    latencia_s: float
    from_cache: bool
    cache_key: str
    tentativas: int
    modelo_efetivo: str = ""
    modo_schema: str = "json_schema"


class ClassificadorMultimodal(Protocol):
    @property
    def identidade(self) -> dict[str, str]: ...

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: list[bytes],
        schema: dict[str, Any],
        nome_schema: str,
        max_tokens: int = 1024,
        usar_cache: bool = True,
    ) -> ResultadoChamada: ...


class ClienteOpenAICompativel:
    """Adaptador único OpenAI-compatível (Gemini AI Studio, OpenAI, Groq, OpenRouter, vLLM/Qwen)."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        max_rpm: int = 10,
        timeout_s: float = 60.0,
        cache_dir: Path = CACHE_DIR,
    ) -> None:
        self._provider = provider
        self._base_url = base_url
        self._model = model
        self._max_rpm = max_rpm
        self._min_interval_s = (60.0 / max_rpm) if max_rpm > 0 else 0.0
        self._last_call_ts = 0.0
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s)

    @property
    def identidade(self) -> dict[str, str]:
        return {"provider": self._provider, "model": self._model, "base_url": self._base_url}

    def _compute_cache_key(
        self,
        system: str,
        user: str,
        imagens_png: list[bytes],
        schema: dict[str, Any],
    ) -> str:
        h = hashlib.sha256()
        h.update(json.dumps(self.identidade, sort_keys=True).encode("utf-8"))
        h.update(system.encode("utf-8"))
        h.update(user.encode("utf-8"))
        h.update(json.dumps(schema, sort_keys=True).encode("utf-8"))
        for img in imagens_png:
            h.update(hashlib.sha256(img).digest())
        return h.hexdigest()

    def _throttle(self) -> None:
        if self._min_interval_s <= 0:
            return
        elapsed = time.monotonic() - self._last_call_ts
        wait = self._min_interval_s - elapsed
        if wait > 0:
            time.sleep(wait)

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: list[bytes],
        schema: dict[str, Any],
        nome_schema: str,
        max_tokens: int = 1024,
        usar_cache: bool = True,
    ) -> ResultadoChamada:
        cache_key = self._compute_cache_key(system, user, imagens_png, schema)
        cache_file = self._cache_dir / f"{cache_key}.json"
        if usar_cache and cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            return ResultadoChamada(
                dados_brutos=cached["dados_brutos"],
                prompt_tokens=cached.get("prompt_tokens", 0),
                completion_tokens=cached.get("completion_tokens", 0),
                latencia_s=cached.get("latencia_s", 0.0),
                from_cache=True,
                cache_key=cache_key,
                tentativas=1,
                modelo_efetivo=cached.get("modelo_efetivo", self._model),
                modo_schema=cached.get("modo_schema", "json_schema"),
            )

        user_content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for img_bytes in imagens_png:
            b64 = base64.b64encode(img_bytes).decode("ascii")
            user_content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max(max_tokens, 4096),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": nome_schema,
                    "schema": schema,
                    "strict": True,
                },
            },
        }
        if self._provider == "vllm_qwen":
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        elif self._provider == "openrouter":
            kwargs["extra_body"] = {"reasoning": {"effort": "low"}}

        modo_schema = "json_schema"
        last_err: Exception | None = None
        for attempt in range(1, 5):
            self._throttle()
            t0 = time.perf_counter()
            try:
                self._last_call_ts = time.monotonic()
                resp = self._client.chat.completions.create(**kwargs)
                lat = round(time.perf_counter() - t0, 2)
                raw_text = (resp.choices[0].message.content or "").strip()
                if not raw_text:
                    raise ValueError("Resposta vazia do modelo (possível consumo total em thinking)")
                # Limpar eventual bloco ```json ... ``` ou texto antes/depois do objeto JSON
                if raw_text.startswith("```"):
                    raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.S).strip()
                if not raw_text.startswith("{"):
                    m_obj = re.search(r"\{.*\}", raw_text, flags=re.S)
                    if m_obj:
                        raw_text = m_obj.group(0)
                dados = json.loads(raw_text)
                usage = getattr(resp, "usage", None)
                pt = getattr(usage, "prompt_tokens", 0) or 0
                ct = getattr(usage, "completion_tokens", 0) or 0
                modelo_efetivo = getattr(resp, "model", None) or self._model

                payload_cache = {
                    "identidade": self.identidade,
                    "modelo_efetivo": modelo_efetivo,
                    "modo_schema": modo_schema,
                    "dados_brutos": dados,
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "latencia_s": lat,
                }
                if usar_cache:
                    cache_file.write_text(
                        json.dumps(payload_cache, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                return ResultadoChamada(
                    dados_brutos=dados,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    latencia_s=lat,
                    from_cache=False,
                    cache_key=cache_key,
                    tentativas=attempt,
                    modelo_efetivo=modelo_efetivo,
                    modo_schema=modo_schema,
                )
            except APIStatusError as exc:
                last_err = exc
                status = exc.status_code
                # Se strict=True/json_schema não for suportado pelo endpoint, degrada para json_object -> prompt_json
                if status in {400, 404} and modo_schema == "json_schema":
                    modo_schema = "json_object"
                    kwargs["response_format"] = {"type": "json_object"}
                    kwargs["messages"][0]["content"] += (
                        "\n\nRETORNE EXCLUSIVAMENTE UM OBJETO JSON VÁLIDO SEGUINDO O SCHEMA:\n"
                        + json.dumps(schema, ensure_ascii=False)
                    )
                    print(f"  [fallback] HTTP {status} com json_schema; tentando json_object...")
                    continue
                if status in {400, 404} and modo_schema == "json_object":
                    modo_schema = "prompt_json"
                    kwargs.pop("response_format", None)
                    print(f"  [fallback] HTTP {status} com json_object; tentando JSON puro via prompt...")
                    continue
                if status in {429, 500, 502, 503, 504}:
                    backoff = min(30.0, 2.5 * (2 ** (attempt - 1)))
                    print(f"  [retry {attempt}/4] HTTP {status}; aguardando {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue
                raise
            except (json.JSONDecodeError, ValueError) as exc:
                last_err = exc
                print(f"  [retry {attempt}/4] JSON inválido: {exc}")
                time.sleep(1.5)

        raise RuntimeError(f"Falha após retries no provedor {self._provider}: {last_err}")


def classificar_com_travas(
    cliente: ClassificadorMultimodal,
    questao: QuestaoExtraida,
    taxonomia: TaxonomiaDef,
    perfil: PerfilClassificacaoDef,
    *,
    enviar_imagens: bool = True,
    usar_cache: bool = True,
) -> dict[str, Any]:
    system, user = montar_prompts(questao, taxonomia, perfil, enviar_imagens=enviar_imagens)
    schema = construir_json_schema_plano(taxonomia)
    imgs_bytes = [p.read_bytes() for p in questao.ativos_visuais] if enviar_imagens else []

    chamada = cliente.classificar_estruturado(
        system=system,
        user=user,
        imagens_png=imgs_bytes,
        schema=schema,
        nome_schema=f"classificacao_{taxonomia.codigo.replace('-', '_')}",
        usar_cache=usar_cache,
    )

    erro_validacao: str | None = None
    validada: ClassificacaoValidada | None = None
    try:
        bruta = SaidaBrutaLLM.model_validate(chamada.dados_brutos)
        validada, erro_validacao = validar_e_normalizar_classificacao(
            bruta, taxonomia, questao.alertas_extracao
        )
    except ValidationError as exc:
        erro_validacao = str(exc)

    retried_correction = False
    if validada is None and erro_validacao:
        # 1 retry corretivo informando explicitamente o erro de catálogo/schema
        retried_correction = True
        user_retry = (
            user
            + f"\n\n[CORREÇÃO OBRIGATÓRIA]: sua resposta anterior falhou na validação ({erro_validacao}). "
            "Retorne novamente o JSON usando EXCLUSIVAMENTE códigos válidos do catálogo."
        )
        chamada = cliente.classificar_estruturado(
            system=system,
            user=user_retry,
            imagens_png=imgs_bytes,
            schema=schema,
            nome_schema=f"classificacao_{taxonomia.codigo.replace('-', '_')}",
            usar_cache=usar_cache,
        )
        bruta = SaidaBrutaLLM.model_validate(chamada.dados_brutos)
        validada, erro_validacao = validar_e_normalizar_classificacao(
            bruta, taxonomia, questao.alertas_extracao
        )

    if validada is None:
        raise RuntimeError(f"Questão {questao.numero} falhou nas travas determinísticas: {erro_validacao}")

    return {
        "questao": questao.numero,
        "taxonomia": taxonomia.codigo,
        "perfil": perfil.versao,
        "enviar_imagens": enviar_imagens,
        "disciplina_principal": validada.disciplina_principal,
        "disciplinas_secundarias": validada.disciplinas_secundarias,
        "topicos": validada.topicos,
        "justificativa": validada.justificativa,
        "confianca": validada.confianca,
        "alertas_validacao": validada.alertas_validacao,
        "requer_revisao_prioritaria": validada.requer_revisao_prioritaria,
        "retried_correction": retried_correction,
        "prompt_tokens": chamada.prompt_tokens,
        "completion_tokens": chamada.completion_tokens,
        "latencia_s": chamada.latencia_s,
        "from_cache": chamada.from_cache,
        "cache_key": chamada.cache_key[:12],
        "modelo_efetivo": chamada.modelo_efetivo,
        "modo_schema": chamada.modo_schema,
    }


# ---------------------------------------------------------------------------
# 5. Testes Sintéticos das Travas Determinísticas (sempre executados)
# ---------------------------------------------------------------------------


def testar_travas_deterministicas() -> list[dict[str, Any]]:
    casos: list[dict[str, Any]] = []

    # Caso 1: Disciplina principal alucinada fora do catálogo -> rejeitada (aciona retry)
    c1 = SaidaBrutaLLM(
        disciplina_principal="robotica-avancada",
        disciplinas_secundarias=[],
        topicos=["PID"],
        justificativa="Alucinação proposital de disciplina fora do catálogo.",
        confianca=0.91,
    )
    val1, err1 = validar_e_normalizar_classificacao(c1, TAXONOMIA_ENADE_V1, [])
    casos.append({
        "caso": "Disciplina principal fora do catálogo (`robotica-avancada`)",
        "esperado": "Rejeitar e acionar retry corretivo",
        "passou": val1 is None and err1 is not None,
        "detalhe": err1 or "Aceitou indevidamente",
    })

    # Caso 2: Secundária duplicando principal + secundária inválida + 3 secundárias + tópicos sujos
    c2 = SaidaBrutaLLM(
        disciplina_principal="redes-e-comunicacoes",
        disciplinas_secundarias=[
            "redes-e-comunicacoes",
            "disciplina-fantasma",
            "sistemas-distribuidos-e-paralelos",
            "seguranca-computacional",
            "algoritmos-e-estruturas-de-dados",
        ],
        topicos=["TCP / UDP", "Sockets!!", "tcp-udp", "Roteamento IP", "Extra 5"],
        justificativa="Teste de saneamento determinístico de secundárias e tópicos.",
        confianca=0.88,
    )
    val2, err2 = validar_e_normalizar_classificacao(c2, TAXONOMIA_ENADE_V1, [])
    ok2 = (
        val2 is not None
        and err2 is None
        and val2.disciplinas_secundarias == ["sistemas-distribuidos-e-paralelos", "seguranca-computacional"]
        and val2.topicos == ["tcp-udp", "sockets", "roteamento-ip", "extra-5"]
        and val2.requer_revisao_prioritaria is True
    )
    casos.append({
        "caso": "Secundária == principal + slug fantasma + >2 secundárias + tópicos não normalizados",
        "esperado": "Sanear secundárias (máx 2 válidas), normalizar/deduplicar tópicos e marcar revisão prioritária",
        "passou": ok2,
        "detalhe": f"sec={val2.disciplinas_secundarias if val2 else None}, topicos={val2.topicos if val2 else None}, alertas={val2.alertas_validacao if val2 else None}",
    })

    # Caso 3: Confiança baixa (< 0.70) ou alerta de extração formula_nao_decodificada
    c3 = SaidaBrutaLLM(
        disciplina_principal="circuitos-e-eletronica",
        disciplinas_secundarias=["matematica-discreta-e-grafos"],
        topicos=["lei-de-kirchhoff", "grafos"],
        justificativa="Alternativas tinham fórmula não decodificada; classificação baseada no enunciado e imagem.",
        confianca=0.64,
    )
    val3, _ = validar_e_normalizar_classificacao(c3, TAXONOMIA_ENADE_V1, ["formula_nao_decodificada"])
    ok3 = val3 is not None and val3.requer_revisao_prioritaria and "baixa_confianca" in val3.alertas_validacao
    casos.append({
        "caso": "Confiança baixa (0.64) + alerta `formula_nao_decodificada`",
        "esperado": "Aceitar sugestão mas sinalizar `requer_revisao_prioritaria=True` e `baixa_confianca`",
        "passou": ok3,
        "detalhe": f"prioritaria={val3.requer_revisao_prioritaria if val3 else None}, alertas={val3.alertas_validacao if val3 else None}",
    })

    return casos


def detectar_divergencia(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Regra de GLOSSARY.md / Ticket 06: divergência apenas quando muda principal ou conjunto de secundárias."""
    return (
        a["disciplina_principal"] != b["disciplina_principal"]
        or set(a["disciplinas_secundarias"]) != set(b["disciplinas_secundarias"])
    )


# ---------------------------------------------------------------------------
# 6. Gerador de Relatório HTML Interativo (inspeção humana)
# ---------------------------------------------------------------------------


def img_to_data_uri(p: Path) -> str:
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def nome_disciplina(tax: TaxonomiaDef, codigo: str) -> str:
    m = tax.mapa_ativas()
    return m[codigo].nome if codigo in m else codigo


def gerar_html(
    *,
    identidade: dict[str, str],
    questoes: list[QuestaoExtraida],
    res_v1: dict[int, dict[str, Any]],
    res_v2: dict[int, dict[str, Any]],
    res_ppc: dict[int, dict[str, Any]],
    ablation: list[dict[str, Any]],
    stability: list[dict[str, Any]],
    travas: list[dict[str, Any]],
    totais: dict[str, Any],
) -> str:
    def badge(txt: str, cls: str = "badge") -> str:
        return f'<span class="{cls}">{html.escape(txt)}</span>'

    def render_pred(pred: dict[str, Any], tax: TaxonomiaDef) -> str:
        pri = pred["disciplina_principal"]
        secs = pred["disciplinas_secundarias"]
        tops = pred["topicos"]
        conf = pred["confianca"]
        conf_cls = "conf-hi" if conf >= 0.85 else ("conf-mid" if conf >= 0.70 else "conf-lo")
        sec_html = " ".join(badge(s, "badge sec") for s in secs) if secs else '<span class="muted">nenhuma</span>'
        top_html = " ".join(badge(t, "badge top") for t in tops)
        alert_html = ""
        if pred["alertas_validacao"] or pred["requer_revisao_prioritaria"]:
            tags = list(pred["alertas_validacao"])
            if pred["requer_revisao_prioritaria"]:
                tags.insert(0, "revisao_prioritaria")
            alert_html = '<div class="alerts">' + " ".join(badge(a, "badge warn") for a in tags) + "</div>"
        return f"""
        <div class="pred-box">
          <div class="pred-head">
            <span class="badge pri" title="{html.escape(nome_disciplina(tax, pri))}">{html.escape(pri)}</span>
            <span class="badge {conf_cls}">conf: {conf:.2f}</span>
            <span class="meta-sm">{pred['prompt_tokens']}→{pred['completion_tokens']} tok · {pred['latencia_s']}s · {html.escape(pred.get('modelo_efetivo', ''))}{' (cache)' if pred['from_cache'] else ''}</span>
          </div>
          <div class="row-sm"><strong>Secundárias:</strong> {sec_html}</div>
          <div class="row-sm"><strong>Tópicos:</strong> {top_html}</div>
          <p class="just">{html.escape(pred['justificativa'])}</p>
          {alert_html}
        </div>
        """

    cards_html: list[str] = []
    divergencias_v1_v2 = 0
    for q in questoes:
        p1 = res_v1[q.numero]
        p2 = res_v2[q.numero]
        pp = res_ppc[q.numero]
        div = detectar_divergencia(p1, p2)
        if div:
            divergencias_v1_v2 += 1
        div_badge = badge("DIVERGÊNCIA v1 × v2", "badge diff") if div else badge("CONCORDANTE v1 = v2", "badge ok")
        ext_alerts = " ".join(badge(a, "badge warn") for a in q.alertas_extracao)
        imgs_html = ""
        if q.ativos_visuais:
            imgs_html = '<div class="img-strip">' + "".join(
                f'<img src="{img_to_data_uri(p)}" alt="Q{q.numero} figura" />' for p in q.ativos_visuais
            ) + "</div>"

        alts_preview = ""
        if q.alternativas:
            alts_preview = "<ul class='alts'>" + "".join(
                f"<li><strong>{k})</strong> {html.escape(v[:180])}{'…' if len(v) > 180 else ''}</li>"
                for k, v in q.alternativas.items()
            ) + "</ul>"

        cards_html.append(f"""
        <section class="card {'has-diff' if div else ''}">
          <div class="card-head">
            <div>
              <h3>Questão {q.numero:02d} <span class="muted">· Gabarito: {html.escape(q.gabarito)}</span></h3>
              <div class="note">{html.escape(q.nota_amostra)}</div>
            </div>
            <div class="badges-right">{div_badge} {ext_alerts}</div>
          </div>
          <details>
            <summary>Ver enunciado extraído ({len(q.enunciado_md)} chars, {len(q.ativos_visuais)} imagem(ns))</summary>
            <pre class="enun">{html.escape(q.enunciado_md)}</pre>
            {alts_preview}
          </details>
          {imgs_html}
          <div class="grid-3">
            <div>
              <h4>Perfil v1 (só ementas · ENADE 18)</h4>
              {render_pred(p1, TAXONOMIA_ENADE_V1)}
            </div>
            <div>
              <h4>Perfil v2 (+14 fronteiras · ENADE 18)</h4>
              {render_pred(p2, TAXONOMIA_ENADE_V1)}
            </div>
            <div>
              <h4>Taxonomia 2 (PPC enxuto · 9 núcleos)</h4>
              {render_pred(pp, TAXONOMIA_PPC_ENXUTO)}
            </div>
          </div>
        </section>
        """)

    ablation_rows = "".join(
        f"""
        <tr>
          <td><strong>Q{a['questao']:02d}</strong></td>
          <td><code>{html.escape(a['com_imagem']['disciplina_principal'])}</code><br><small>sec: {html.escape(', '.join(a['com_imagem']['disciplinas_secundarias']) or '—')} · conf: {a['com_imagem']['confianca']:.2f}</small><p class="just-sm">{html.escape(a['com_imagem']['justificativa'])}</p></td>
          <td><code>{html.escape(a['sem_imagem']['disciplina_principal'])}</code><br><small>sec: {html.escape(', '.join(a['sem_imagem']['disciplinas_secundarias']) or '—')} · conf: {a['sem_imagem']['confianca']:.2f}</small><p class="just-sm">{html.escape(a['sem_imagem']['justificativa'])}</p></td>
          <td>{badge('MUDOU', 'badge diff') if a['mudou'] else badge('IGUAL', 'badge ok')}<br><small>Δ tokens prompt: +{a['delta_prompt_tokens']}</small></td>
        </tr>
        """
        for a in ablation
    )

    stability_rows = "".join(
        f"""
        <tr>
          <td><strong>Q{s['questao']:02d}</strong></td>
          <td><code>{html.escape(s['passada_1']['disciplina_principal'])}</code> ({html.escape(', '.join(s['passada_1']['disciplinas_secundarias']) or '—')}) · conf {s['passada_1']['confianca']:.2f}</td>
          <td><code>{html.escape(s['passada_2']['disciplina_principal'])}</code> ({html.escape(', '.join(s['passada_2']['disciplinas_secundarias']) or '—')}) · conf {s['passada_2']['confianca']:.2f}</td>
          <td>{badge('ESTÁVEL', 'badge ok') if not s['divergiu'] else badge('VARIOU', 'badge diff')}</td>
        </tr>
        """
        for s in stability
    )

    travas_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(t['caso'])}</td>
          <td>{html.escape(t['esperado'])}</td>
          <td>{badge('PASSOU', 'badge ok') if t['passou'] else badge('FALHOU', 'badge diff')}</td>
          <td><code>{html.escape(t['detalhe'])}</code></td>
        </tr>
        """
        for t in travas
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<title>Protótipo 07 — Classificação Multimodal ENADE 2023</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; line-height: 1.45; }}
  h1, h2, h3, h4 {{ margin: 0 0 8px 0; }}
  .wrap {{ max-width: 1380px; margin: 0 auto; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 16px 0 24px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 14px; }}
  .kpi .val {{ font-size: 1.5rem; font-weight: 700; color: #38bdf8; }}
  .kpi .lbl {{ font-size: 0.82rem; color: #94a3b8; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 18px; }}
  .card.has-diff {{ border-left: 4px solid #f59e0b; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }}
  .note {{ font-size: 0.86rem; color: #94a3b8; }}
  .muted {{ color: #94a3b8; font-weight: 400; }}
  .grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }}
  @media (max-width: 1024px) {{ .grid-3 {{ grid-template-columns: 1fr; }} }}
  .pred-box {{ background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px; height: 100%; box-sizing: border-box; }}
  .pred-head {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 8px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.76rem; font-weight: 600; background: #334155; color: #e2e8f0; }}
  .badge.pri {{ background: #1d4ed8; color: #fff; }}
  .badge.sec {{ background: #4338ca; color: #e0e7ff; }}
  .badge.top {{ background: #1e293b; border: 1px solid #475569; color: #cbd5e1; font-weight: 500; }}
  .badge.ok {{ background: #065f46; color: #d1fae5; }}
  .badge.diff {{ background: #92400e; color: #fef3c7; }}
  .badge.warn {{ background: #7f1d1d; color: #fecaca; }}
  .badge.conf-hi {{ background: #065f46; color: #d1fae5; }}
  .badge.conf-mid {{ background: #854d0e; color: #fef08a; }}
  .badge.conf-lo {{ background: #991b1b; color: #fee2e2; }}
  .meta-sm {{ font-size: 0.74rem; color: #94a3b8; margin-left: auto; }}
  .row-sm {{ font-size: 0.82rem; margin: 4px 0; }}
  .just {{ font-size: 0.84rem; color: #cbd5e1; margin: 8px 0 0; }}
  .just-sm {{ font-size: 0.8rem; color: #cbd5e1; margin: 4px 0 0; }}
  .alerts {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
  .img-strip {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }}
  .img-strip img {{ max-height: 220px; max-width: 100%; background: #fff; border-radius: 6px; padding: 4px; }}
  details {{ margin: 6px 0; }}
  summary {{ cursor: pointer; font-size: 0.85rem; color: #38bdf8; }}
  pre.enun {{ white-space: pre-wrap; background: #0b1220; padding: 10px; border-radius: 6px; font-size: 0.82rem; max-height: 260px; overflow: auto; }}
  ul.alts {{ font-size: 0.82rem; margin: 6px 0 0 18px; padding: 0; color: #cbd5e1; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0 24px; background: #1e293b; border-radius: 10px; overflow: hidden; }}
  th, td {{ border-bottom: 1px solid #334155; padding: 10px; text-align: left; vertical-align: top; font-size: 0.85rem; }}
  th {{ background: #0b1220; color: #94a3b8; }}
  code {{ background: #0f172a; padding: 2px 5px; border-radius: 4px; font-size: 0.82rem; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Protótipo 07 — Classificação Multimodal, Perfis e Reclassificação (ENADE 2023)</h1>
  <p class="muted">Provedor: <code>{html.escape(identidade['provider'])}</code> · Modelo: <code>{html.escape(identidade['model'])}</code> · Endpoint: <code>{html.escape(identidade['base_url'])}</code></p>

  <div class="kpi-grid">
    <div class="kpi"><div class="val">{len(questoes)}</div><div class="lbl">Questões reais ENADE 2023 (7 c/ imagem)</div></div>
    <div class="kpi"><div class="val">{totais['total_chamadas']}</div><div class="lbl">Chamadas totais ({totais['cache_hits']} cache hits)</div></div>
    <div class="kpi"><div class="val">{divergencias_v1_v2} / {len(questoes)}</div><div class="lbl">Divergências Perfil v1 × v2</div></div>
    <div class="kpi"><div class="val">{totais['prompt_tokens']:,} / {totais['completion_tokens']:,}</div><div class="lbl">Tokens (prompt / saída)</div></div>
    <div class="kpi"><div class="val">{totais['latencia_media_s']:.2f}s</div><div class="lbl">Latência média / chamada</div></div>
    <div class="kpi"><div class="val">{sum(1 for t in travas if t['passou'])} / {len(travas)}</div><div class="lbl">Travas determinísticas (testes sintéticos)</div></div>
  </div>

  <h2>1. Comparação por Questão (Perfil v1 × Perfil v2 × Taxonomia PPC)</h2>
  {"".join(cards_html)}

  <h2>2. Ablação Multimodal (Com Imagem vs Sem Imagem — Perfil v2)</h2>
  <table>
    <thead><tr><th>Questão</th><th>Com Imagem (Multimodal)</th><th>Sem Imagem (Só Texto)</th><th>Impacto</th></tr></thead>
    <tbody>{ablation_rows}</tbody>
  </table>

  <h2>3. Estabilidade em <code>temperature=0</code> (2ª passada sem cache — Perfil v2)</h2>
  <table>
    <thead><tr><th>Questão</th><th>Passada 1</th><th>Passada 2 (sem cache)</th><th>Resultado</th></tr></thead>
    <tbody>{stability_rows}</tbody>
  </table>

  <h2>4. Travas Determinísticas Pós-LLM (Casos Sintéticos de Falha)</h2>
  <table>
    <thead><tr><th>Cenário de falha</th><th>Comportamento esperado</th><th>Status</th><th>Evidência</th></tr></thead>
    <tbody>{travas_rows}</tbody>
  </table>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 7. CLI principal
# ---------------------------------------------------------------------------


def resolver_config_llm() -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    provider = os.getenv("LLM_PROVIDER", "gemini_openai").strip()
    api_key = (os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    base_url = os.getenv(
        "LLM_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ).strip()
    model = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite").strip()
    max_rpm = int(os.getenv("LLM_MAX_RPM", "10"))
    timeout_s = float(os.getenv("LLM_TIMEOUT_S", "60"))
    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "max_rpm": max_rpm,
        "timeout_s": timeout_s,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Protótipo 07 — Classificação Multimodal ENADE 2023")
    parser.add_argument("--dry-run", action="store_true", help="Valida amostra, imagens, schemas e travas sem chamar API")
    parser.add_argument("--smoke", action="store_true", help="Executa apenas 1 chamada real (Q23 com imagem) para validar conectividade")
    parser.add_argument("--budget-free", action="store_true", help="Usa 10 questões (~34 chamadas) para caber no limite de 50 RPD do OpenRouter :free")
    parser.add_argument("--full", action="store_true", help="Força amostra completa de 14 questões (48 chamadas)")
    parser.add_argument("--no-cache", action="store_true", help="Ignora cache em disco na execução")
    parser.add_argument("--model", type=str, default=None, help="Sobrescreve LLM_MODEL do .env")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = resolver_config_llm()
    if args.model:
        cfg["model"] = args.model
    auto_free = (not args.full) and (args.budget_free or (":free" in cfg["model"] or cfg["model"] == "openrouter/free"))
    sample_nums = SAMPLE_NUMBERS_FREE if auto_free else SAMPLE_NUMBERS
    ablation_nums = ABLATION_IMAGE_NUMBERS_FREE if auto_free else ABLATION_IMAGE_NUMBERS
    stability_nums = STABILITY_NUMBERS_FREE if auto_free else STABILITY_NUMBERS

    questoes = carregar_questoes_2023(sample_nums)
    print(f"[amostra] {len(questoes)}/{len(sample_nums)} questões carregadas do Docling 2023 (modo_free={auto_free}):")
    for q in questoes:
        print(
            f"  Q{q.numero:02d} | gab={q.gabarito} | imgs={len(q.ativos_visuais)} "
            f"| alts={len(q.alternativas)} | alertas={q.alertas_extracao}"
        )

    travas = testar_travas_deterministicas()
    print("\n[travas determinísticas]")
    for t in travas:
        print(f"  {'OK' if t['passou'] else 'FAIL'} | {t['caso']} -> {t['detalhe']}")
    if not all(t["passou"] for t in travas):
        raise SystemExit("Falha em teste de trava determinística!")

    schema_enade = construir_json_schema_plano(TAXONOMIA_ENADE_V1)
    schema_ppc = construir_json_schema_plano(TAXONOMIA_PPC_ENXUTO)
    print(f"\n[schemas] ENADE enum={len(schema_enade['properties']['disciplina_principal']['enum'])} | PPC enum={len(schema_ppc['properties']['disciplina_principal']['enum'])}")

    if args.dry_run:
        sys_p, usr_p = montar_prompts(questoes[0], TAXONOMIA_ENADE_V1, PERFIL_V2_FRONTEIRAS, enviar_imagens=True)
        print(f"[dry-run] Prompt v2 Q{questoes[0].numero:02d}: system={len(sys_p)} chars, user={len(usr_p)} chars")
        print("[dry-run] Tudo pronto! Configure GEMINI_API_KEY no .env e rode sem --dry-run.")
        return

    if not cfg["api_key"]:
        raise SystemExit(
            "Erro: nenhuma chave configurada. Defina GEMINI_API_KEY (ou LLM_API_KEY) no arquivo .env na raiz do projeto."
        )

    cliente = ClienteOpenAICompativel(
        provider=cfg["provider"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        max_rpm=cfg["max_rpm"],
        timeout_s=cfg["timeout_s"],
    )
    usar_cache = not args.no_cache
    print(f"\n[execução] {cliente.identidade} | max_rpm={cfg['max_rpm']} | cache={usar_cache}")

    if args.smoke:
        q23 = next(q for q in questoes if q.numero == 23)
        r = classificar_com_travas(cliente, q23, TAXONOMIA_ENADE_V1, PERFIL_V2_FRONTEIRAS, enviar_imagens=True, usar_cache=usar_cache)
        print("[smoke] Resultado Q23:", json.dumps(r, ensure_ascii=False, indent=2))
        return

    todas_chamadas: list[dict[str, Any]] = []
    res_v1: dict[int, dict[str, Any]] = {}
    res_v2: dict[int, dict[str, Any]] = {}
    res_ppc: dict[int, dict[str, Any]] = {}

    print("\n--- Rodada 1/3: ENADE 18 disciplinas · Perfil v1 (só ementas) ---")
    for q in questoes:
        r = classificar_com_travas(cliente, q, TAXONOMIA_ENADE_V1, PERFIL_V1_EMENTAS, enviar_imagens=True, usar_cache=usar_cache)
        res_v1[q.numero] = r
        todas_chamadas.append(r)
        print(f"  Q{q.numero:02d} -> {r['disciplina_principal']} | sec={r['disciplinas_secundarias']} | conf={r['confianca']:.2f} ({r['latencia_s']}s{' cache' if r['from_cache'] else ''})")

    print("\n--- Rodada 2/3: ENADE 18 disciplinas · Perfil v2 (+14 fronteiras) ---")
    for q in questoes:
        r = classificar_com_travas(cliente, q, TAXONOMIA_ENADE_V1, PERFIL_V2_FRONTEIRAS, enviar_imagens=True, usar_cache=usar_cache)
        res_v2[q.numero] = r
        todas_chamadas.append(r)
        div = " [DIVERGIU v1]" if detectar_divergencia(res_v1[q.numero], r) else ""
        print(f"  Q{q.numero:02d} -> {r['disciplina_principal']} | sec={r['disciplinas_secundarias']} | conf={r['confianca']:.2f}{div}")

    print("\n--- Rodada 3/3: Segunda Taxonomia (PPC enxuto 9 núcleos) ---")
    for q in questoes:
        r = classificar_com_travas(cliente, q, TAXONOMIA_PPC_ENXUTO, PERFIL_PPC_V1, enviar_imagens=True, usar_cache=usar_cache)
        res_ppc[q.numero] = r
        todas_chamadas.append(r)
        print(f"  Q{q.numero:02d} -> {r['disciplina_principal']} | sec={r['disciplinas_secundarias']} | conf={r['confianca']:.2f}")

    print(f"\n--- Experimento A: Ablação Multimodal (sem imagem em {ablation_nums}) ---")
    ablation: list[dict[str, Any]] = []
    q_by_num = {q.numero: q for q in questoes}
    for n in ablation_nums:
        q = q_by_num[n]
        sem_img = classificar_com_travas(cliente, q, TAXONOMIA_ENADE_V1, PERFIL_V2_FRONTEIRAS, enviar_imagens=False, usar_cache=usar_cache)
        todas_chamadas.append(sem_img)
        com_img = res_v2[n]
        mudou = detectar_divergencia(com_img, sem_img)
        ablation.append({
            "questao": n,
            "com_imagem": com_img,
            "sem_imagem": sem_img,
            "mudou": mudou,
            "delta_prompt_tokens": com_img["prompt_tokens"] - sem_img["prompt_tokens"],
        })
        print(f"  Q{n:02d} | com={com_img['disciplina_principal']} vs sem={sem_img['disciplina_principal']} | mudou={mudou} | Δprompt_tok={com_img['prompt_tokens'] - sem_img['prompt_tokens']}")

    print(f"\n--- Experimento B: Estabilidade em temperature=0 (2ª passada sem cache em {stability_nums}) ---")
    stability: list[dict[str, Any]] = []
    for n in stability_nums:
        q = q_by_num[n]
        p2 = classificar_com_travas(cliente, q, TAXONOMIA_ENADE_V1, PERFIL_V2_FRONTEIRAS, enviar_imagens=True, usar_cache=False)
        todas_chamadas.append(p2)
        p1 = res_v2[n]
        divergiu = detectar_divergencia(p1, p2)
        stability.append({"questao": n, "passada_1": p1, "passada_2": p2, "divergiu": divergiu})
        print(f"  Q{n:02d} | p1={p1['disciplina_principal']}({p1['disciplinas_secundarias']}) vs p2={p2['disciplina_principal']}({p2['disciplinas_secundarias']}) | divergiu={divergiu}")

    totais = {
        "total_chamadas": len(todas_chamadas),
        "cache_hits": sum(1 for c in todas_chamadas if c["from_cache"]),
        "prompt_tokens": sum(c["prompt_tokens"] for c in todas_chamadas),
        "completion_tokens": sum(c["completion_tokens"] for c in todas_chamadas),
        "latencia_media_s": round(sum(c["latencia_s"] for c in todas_chamadas) / max(len(todas_chamadas), 1), 2),
        "divergencias_v1_v2": sum(1 for q in questoes if detectar_divergencia(res_v1[q.numero], res_v2[q.numero])),
        "ablation_mudou": sum(1 for a in ablation if a["mudou"]),
        "stability_estavel": sum(1 for s in stability if not s["divergiu"]),
    }

    summary = {
        "identidade": cliente.identidade,
        "totais": totais,
        "res_v1": res_v1,
        "res_v2": res_v2,
        "res_ppc": res_ppc,
        "ablation": ablation,
        "stability": stability,
        "travas": travas,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    html_doc = gerar_html(
        identidade=cliente.identidade,
        questoes=questoes,
        res_v1=res_v1,
        res_v2=res_v2,
        res_ppc=res_ppc,
        ablation=ablation,
        stability=stability,
        travas=travas,
        totais=totais,
    )
    html_path = OUT_DIR / "relatorio-classificacao.html"
    html_path.write_text(html_doc, encoding="utf-8")
    print(f"\n[concluído] Summary: {OUT_DIR / 'summary.json'}")
    print(f"[concluído] Painel HTML: {html_path}")


if __name__ == "__main__":
    main()
