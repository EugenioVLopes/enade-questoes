"""Seed inicial canônico e idempotente (Taxonomia ENADE EC + Perfil v2-fronteiras)."""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.repositorios import (
    RepositorioPerfisClassificacao,
    RepositorioTaxonomias,
)
from domain.classificacao import PerfilClassificacao
from domain.taxonomia import Disciplina, Taxonomia

CODIGO_TAXONOMIA_PADRAO = "enade-eng-computacao"
NOME_TAXONOMIA_PADRAO = "ENADE Engenharia de Computação"
CURSO_REFERENCIA_PADRAO = "Engenharia de Computação"

CODIGO_PERFIL_PADRAO = "v2-fronteiras"
VERSAO_PERFIL_PADRAO = "v1"
DESCRICAO_PERFIL_PADRAO = (
    "Prompt com ementas canônicas + guia editorial de 14 fronteiras interdisciplinares + regra anti-distrator"
)

DISCIPLINAS_PADRAO: tuple[tuple[str, str, str], ...] = (
    (
        "matematica-e-estatistica",
        "Matemática, Probabilidade e Estatística",
        (
            "Cálculo diferencial/integral, equações diferenciais, álgebra linear, cálculo numérico, "
            "probabilidade, variáveis aleatórias, inferência e estatística aplicada."
        ),
    ),
    (
        "fisica-e-materiais",
        "Física e Ciência dos Materiais",
        (
            "Mecânica, eletromagnetismo, ondas/óptica, termodinâmica básica, propriedades "
            "elétricas/semicondutoras de materiais e fundamentos físicos de Engenharia "
            "(inclui itens residuais do núcleo comum de 2017: química, mecânica dos sólidos e "
            "fenômenos de transporte)."
        ),
    ),
    (
        "matematica-discreta-e-grafos",
        "Matemática Discreta, Lógica e Teoria dos Grafos",
        (
            "Lógica proposicional e de predicados, conjuntos, relações, indução, combinatória, "
            "recorrências, teoria dos números e teoria dos grafos (caminhos, árvores, conectividade, coloração)."
        ),
    ),
    (
        "pesquisa-operacional-e-otimizacao",
        "Pesquisa Operacional e Otimização",
        (
            "Programação linear (modelagem, Simplex, dualidade), programação inteira, "
            "otimização combinatória, fluxos em redes, teoria de filas e simulação de eventos discretos."
        ),
    ),
    (
        "algoritmos-e-estruturas-de-dados",
        "Algoritmos, Programação e Estruturas de Dados",
        (
            "Paradigmas e fundamentos de programação (estruturada, OO, funcional), estruturas "
            "lineares/árvores/hashing/heaps, ordenação, busca, projeto e análise de complexidade "
            "de algoritmos (divisão e conquista, guloso, programação dinâmica)."
        ),
    ),
    (
        "linguagens-formais-e-compiladores",
        "Linguagens Formais, Autômatos e Compiladores",
        (
            "Hierarquia de Chomsky, expressões regulares, autômatos finitos e de pilha, gramáticas "
            "livres de contexto, máquinas de Turing, decidibilidade/computabilidade e fases de compilação "
            "(análise léxica, sintática, semântica e geração de código)."
        ),
    ),
    (
        "engenharia-de-software-e-ihc",
        "Engenharia de Software e Interação Humano-Computador",
        (
            "Processos e ciclo de vida (ágeis e tradicionais), engenharia de requisitos, modelagem (UML), "
            "arquitetura e padrões de projeto, qualidade, verificação/validação/testes, manutenção, "
            "usabilidade, acessibilidade e avaliação de IHC."
        ),
    ),
    (
        "banco-de-dados",
        "Banco de Dados",
        (
            "Modelagem conceitual (MER/EER), modelo relacional, álgebra relacional, SQL, normalização, "
            "indexação, processamento de consultas, transações (ACID), controle de concorrência, "
            "recuperação e bancos NoSQL."
        ),
    ),
    (
        "circuitos-e-eletronica",
        "Circuitos Elétricos e Eletrônica",
        (
            "Leis de Kirchhoff, análise nodal/malhas, teoremas (Thévenin/Norton), circuitos RC/RL/RLC "
            "(DC/AC, fasores), diodos, transistores (BJT/MOSFET), amplificadores operacionais, fontes "
            "e condicionamento analógico de sinais."
        ),
    ),
    (
        "sistemas-digitais-e-embarcados",
        "Sistemas Digitais e Sistemas Embarcados",
        (
            "Álgebra booleana, simplificação (Karnaugh), circuitos combinacionais e sequenciais "
            "(flip-flops, contadores, FSMs), VHDL/Verilog/FPGA, microcontroladores, interfaces/periféricos "
            "(GPIO, PWM, ADC/DAC, UART/SPI/I2C), firmware e sistemas de tempo real."
        ),
    ),
    (
        "arquitetura-de-computadores",
        "Organização e Arquitetura de Computadores",
        (
            "Representação de dados e aritmética computacional, conjunto de instruções (ISA), caminho de "
            "dados e controle, pipeline e hazards, hierarquia de memória (cache), E/S, DMA, arquiteturas "
            "superescalares, multicore e avaliação de desempenho (CPI, lei de Amdahl)."
        ),
    ),
    (
        "sistemas-operacionais",
        "Sistemas Operacionais",
        (
            "Processos e threads, escalonamento de CPU (incluindo tempo real), sincronização e concorrência "
            "(semáforos, mutex, deadlock), gerência de memória (paginação, segmentação, memória virtual), "
            "sistemas de arquivos, gerência de E/S e virtualização."
        ),
    ),
    (
        "redes-e-comunicacoes",
        "Redes de Computadores e Sistemas de Comunicação",
        (
            "Camada física e princípios de telecomunicações (modulação, multiplexação, meios de transmissão), "
            "modelos OSI e TCP/IP, enlace/Ethernet/Wi-Fi, roteamento e endereçamento IP (CIDR/sub-redes), "
            "transporte (TCP/UDP, controle de congestionamento) e protocolos de aplicação (DNS, HTTP)."
        ),
    ),
    (
        "sistemas-distribuidos-e-paralelos",
        "Sistemas Distribuídos e Processamento Paralelo",
        (
            "Arquiteturas paralelas (memória compartilhada/distribuída, OpenMP, MPI, GPU), comunicação entre "
            "processos (RPC, REST, mensageria), relógios lógicos, coordenação/consenso, tolerância a falhas, "
            "replicação, consistência e computação em nuvem."
        ),
    ),
    (
        "seguranca-computacional",
        "Segurança de Sistemas de Computação",
        (
            "Tríade CIA, criptografia simétrica e assimétrica, hashes, assinatura digital e PKI/certificados, "
            "autenticação e controle de acesso, segurança de redes (TLS, firewall, IDS/VPN), vulnerabilidades "
            "de software/web e gestão de riscos/normas (LGPD, ISO 27001)."
        ),
    ),
    (
        "ia-e-ciencia-de-dados",
        "Inteligência Artificial e Ciência de Dados",
        (
            "Busca heurística, representação de conhecimento, aprendizado de máquina (supervisionado, não "
            "supervisionado, redes neurais), avaliação de modelos, ciência de dados (coleta, limpeza, "
            "análise exploratória, mineração e visualização de dados)."
        ),
    ),
    (
        "sinais-controle-e-automacao",
        "Processamento de Sinais, Controle e Automação",
        (
            "Sinais e sistemas lineares invariantes no tempo, séries/transformadas de Fourier, Laplace e Z, "
            "teorema da amostragem, filtros digitais/DSP, modelagem de sistemas dinâmicos, função de "
            "transferência, estabilidade, controladores (PID), automação industrial (CLPs, sensores/atuadores, SCADA)."
        ),
    ),
    (
        "gestao-viabilidade-e-etica",
        "Gestão de Projetos, Viabilidade Técnico-Econômica e Ética Profissional",
        (
            "Gestão de projetos e ciclo de vida, estudos de viabilidade técnica/social/econômica (engenharia "
            "econômica: VPL, TIR, payback), administração/empreendedorismo, metodologia científica, propriedade "
            "intelectual, legislação profissional, ética e sustentabilidade ambiental."
        ),
    ),
)

DIRETRIZES_GERAIS_PADRAO = (
    "Você é um especialista acadêmico em Engenharia de Computação encarregado de classificar "
    "questões objetivas do ENADE segundo a Taxonomia fornecida.\n"
    "Analise integralmente o enunciado, todas as alternativas e todas as imagens anexadas (se houver).\n"
    "Escolha EXATAMENTE 1 `disciplina_principal` entre os códigos ativos da Taxonomia e de 0 a 2 "
    "`disciplinas_secundarias` (somente se a questão realmente cobrar conteúdo substancial da disciplina secundária).\n"
    "Gere de 1 a 4 `topicos` curtos em kebab-case sem acentos (ex.: 'memoria-virtual', 'filtro-passa-baixa').\n"
    "Forneça uma `justificativa` técnica concisa (2 a 4 frases) citando evidências concretas do enunciado/imagem.\n"
    "Informe `confianca` entre 0.0 e 1.0 "
    "(use < 0.75 quando houver ambiguidade forte ou informação ilegível/incompleta)."
)

GUIA_FRONTEIRAS_PADRAO = "\n".join(
    [
        "GUIA EDITORIAL DE DESAMBIGUAÇÃO DE FRONTEIRAS "
        "(siga rigorosamente ao escolher disciplina_principal vs disciplinas_secundarias):",
        "1. Organização e Arquitetura de Computadores × Sistemas Operacionais:",
        "   - Memória virtual, paginação/TLB, hierarquia de cache, DMA, interrupções e escalonamento multicore:",
        "     foco em hardware, endereçamento físico/cache, pipeline ou métricas de CPU (CPI/miss rate) -> "
        "`arquitetura-de-computadores`;",
        "     foco em políticas de escalonamento, tabelas de páginas, troca de contexto (MMU/TLB) ou "
        "sincronização do kernel -> `sistemas-operacionais`.",
        "2. Circuitos Elétricos e Eletrônica × Sistemas Digitais e Embarcados:",
        "   - Portas lógicas em nível transistor (CMOS/TTL), conversores ADC/DAC, condicionamento de sensores, PWM:",
        "     exige análise de tensões, correntes, resistência/resistividade, ganho ou resposta analógica -> "
        "`circuitos-e-eletronica`;",
        "     exige lógica booleana, registradores GPIO, manipulação bitwise de registradores, resolução em bits, "
        "temporização digital ou periféricos -> `sistemas-digitais-e-embarcados`.",
        "3. Sistemas Digitais e Embarcados × Organização e Arquitetura de Computadores:",
        "   - ULA, datapath, unidade de controle/FSM, barramentos, FPGA/SoC:",
        "     foco em síntese lógica, portas, flip-flops, FSM, HDL (VHDL/Verilog) ou microcontrolador -> "
        "`sistemas-digitais-e-embarcados`;",
        "     foco em ISA, pipeline, organização de processadores de propósito geral e desempenho -> "
        "`arquitetura-de-computadores`.",
        "4. Sistemas Digitais e Embarcados × Sistemas Operacionais:",
        "   - RTOS, escalonamento de tempo real (RM/EDF), tratamento de interrupções (ISR), drivers e deadlines:",
        "     foco em hardware/periféricos/firmware embarcado -> `sistemas-digitais-e-embarcados`;",
        "     foco em algoritmos de escalonamento, inversão de prioridade ou abstrações de kernel -> "
        "`sistemas-operacionais`.",
        "5. Redes de Computadores e Sistemas de Comunicação × Sistemas Distribuídos e Processamento Paralelo:",
        "   - Sockets, RPC/REST, balanceamento de carga, latência, replicação e tolerância a falhas:",
        "     camadas OSI/TCP-IP, roteamento (ex.: OSPF), sub-redes ou comparação estrutural TCP vs UDP -> "
        "`redes-e-comunicacoes` (mesmo que cite sistemas distribuídos como contexto, que entram como secundária);",
        "     coordenação, consenso, consistência, paralelismo, nuvem ou arquitetura distribuída -> "
        "`sistemas-distribuidos-e-paralelos`.",
        "6. Redes de Computadores e Sistemas de Comunicação × Segurança de Sistemas de Computação:",
        "   - TLS/HTTPS, VPN, firewalls, ataques de rede (DDoS, MITM, spoofing), autenticação e PKI:",
        "     objetivo avaliado é vulnerabilidade, confidencialidade/integridade/autenticidade ou criptografia -> "
        "`seguranca-computacional`;",
        "     foco no funcionamento estrutural do protocolo de rede -> `redes-e-comunicacoes`.",
        "7. Sistemas Operacionais × Sistemas Distribuídos e Processamento Paralelo:",
        "   - Threads, exclusão mútua, deadlock, OpenMP/MPI, virtualização e contêineres:",
        "     concorrência em nó único / gerência local de recursos -> `sistemas-operacionais`;",
        "     paralelismo de alto desempenho (speedup/escalabilidade em múltiplos nós) ou sistemas distribuídos -> "
        "`sistemas-distribuidos-e-paralelos`.",
        "8. Algoritmos, Programação e Estruturas de Dados × Matemática Discreta, Lógica e Teoria dos Grafos:",
        "   - Algoritmos em grafos (BFS/DFS, Dijkstra, árvores geradoras), relações de equivalência e recorrências:",
        "     foco em propriedade estrutural/formal (reflexividade, simetria, transitividade), lógica ou prova -> "
        "`matematica-discreta-e-grafos`;",
        "     foco em implementação, estruturas de dados (pilha/fila/vetor/árvore), análise de complexidade ou "
        "rastreio algorítmico em C (malloc/free mesmo em contexto embarcado) -> `algoritmos-e-estruturas-de-dados`.",
        "9. Algoritmos, Programação e Estruturas de Dados × Pesquisa Operacional e Otimização:",
        "   - Programação dinâmica, algoritmos gulosos, branch-and-bound, meta-heurísticas e fluxos:",
        "     formulação de modelo matemático de decisão (função objetivo, restrições, Simplex, filas) -> "
        "`pesquisa-operacional-e-otimizacao`;",
        "     foco em técnica algorítmica e complexidade -> `algoritmos-e-estruturas-de-dados`.",
        "10. Matemática, Probabilidade e Estatística × Inteligência Artificial e Ciência de Dados:",
        "   - Regressão, probabilidade bayesiana, álgebra linear (PCA/matrizes), métricas e validação:",
        "     avalia teoria/cálculo probabilístico ou estatístico geral -> `matematica-e-estatistica`;",
        "     avalia pipeline de dados, aprendizado de máquina ou busca heurística (busca gulosa, A*) -> "
        "`ia-e-ciencia-de-dados` (com `algoritmos-e-estruturas-de-dados` ou `matematica-discreta-e-grafos` "
        "como secundária quando aplicável).",
        "11. Banco de Dados × Inteligência Artificial e Ciência de Dados:",
        "   - Data warehouse, OLAP, consultas analíticas SQL, ETL e mineração de dados:",
        "     modelagem, integridade, SQL e armazenamento/indexação -> `banco-de-dados`;",
        "     modelagem preditiva, descoberta de padrões ou análise exploratória -> `ia-e-ciencia-de-dados`.",
        "12. Circuitos Elétricos e Eletrônica × Processamento de Sinais, Controle e Automação:",
        "   - Circuitos RLC modelados por Laplace, filtros analógicos vs digitais, diagrama de Bode:",
        "     cálculo de grandezas elétricas, topologia com AmpOp, impedância ou filtros analógicos RC/AmpOp -> "
        "`circuitos-e-eletronica` (com `sinais-controle-e-automacao` como secundária se envolver corte/frequência);",
        "     análise abstrata de resposta em frequência, transformadas, amostragem, estabilidade ou PID -> "
        "`sinais-controle-e-automacao`.",
        "13. Linguagens Formais, Autômatos e Compiladores × Sistemas Digitais e Embarcados:",
        "   - Máquinas de Estados Finitos (Mealy/Moore), minimização de estados e reconhecimento de sequências:",
        "     reconhecimento de linguagens/gramáticas/análise léxica -> `linguagens-formais-e-compiladores`;",
        "     síntese de circuito sequencial com flip-flops/HDL -> `sistemas-digitais-e-embarcados`.",
        "14. Engenharia de Software e IHC × Banco de Dados / Segurança Computacional / Gestão, Viabilidade e Ética:",
        "   - Modelagem UML × MER, requisitos de segurança, cronograma/custos de projeto de software:",
        "     engenharia de requisitos, arquitetura, testes e usabilidade -> `engenharia-de-software-e-ihc`;",
        "     viabilidade financeira/gestão corporativa/propriedade intelectual -> `gestao-viabilidade-e-etica`.",
        "15. Regra anti-distrator de contexto:",
        "   - Questões do ENADE frequentemente usam um cenário prático como pano de fundo (ex.: cluster para cobrar "
        "relação de equivalência, ou controlador PID para cobrar fila/pilha). Classifique como "
        "`disciplina_principal` o CONHECIMENTO TÉCNICO EFETIVAMENTE EXIGIDO PARA RESOLVER AS ALTERNATIVAS.",
    ]
)

TEMPLATE_PROMPT_PADRAO = (
    "[SYSTEM]\n"
    "{diretrizes_gerais}\n\n"
    "TAXONOMIA ATIVA: {taxonomia_nome} (`{taxonomia_codigo}`)\n"
    "CATÁLOGO FECHADO DE DISCIPLINAS PERMITIDAS (use SOMENTE estes códigos):\n"
    "{catalogo_disciplinas}\n\n"
    "{guia_fronteiras}\n\n"
    "[USER]\n"
    "QUESTÃO {numero:02d} ({exame} {ano} — {curso} — {componente})\n"
    "{bloco_alertas_extracao}\n"
    "ENUNCIADO:\n"
    "{enunciado}\n\n"
    "ALTERNATIVAS:\n"
    "{alternativas}\n"
    "{bloco_ativos_visuais}"
)


@dataclass(frozen=True, slots=True)
class ResultadoSeed:
    taxonomia: Taxonomia
    perfil: PerfilClassificacao
    taxonomia_criada: bool
    perfil_criado: bool


def criar_taxonomia_inicial() -> Taxonomia:
    disciplinas = [
        Disciplina(codigo=codigo, nome=nome, ementa=ementa, ativa=True) for codigo, nome, ementa in DISCIPLINAS_PADRAO
    ]
    return Taxonomia(
        codigo=CODIGO_TAXONOMIA_PADRAO,
        nome=NOME_TAXONOMIA_PADRAO,
        curso_referencia=CURSO_REFERENCIA_PADRAO,
        disciplinas=disciplinas,
    )


def criar_perfil_inicial() -> PerfilClassificacao:
    return PerfilClassificacao(
        codigo=CODIGO_PERFIL_PADRAO,
        versao=VERSAO_PERFIL_PADRAO,
        descricao=DESCRICAO_PERFIL_PADRAO,
        diretrizes_gerais=DIRETRIZES_GERAIS_PADRAO,
        guia_fronteiras=GUIA_FRONTEIRAS_PADRAO,
        template_prompt=TEMPLATE_PROMPT_PADRAO,
    )


def executar_seed_inicial(
    repo_taxonomias: RepositorioTaxonomias,
    repo_perfis: RepositorioPerfisClassificacao,
) -> ResultadoSeed:
    """Garante a existência da Taxonomia e do Perfil de Classificação iniciais de forma 100% idempotente."""
    taxonomia = repo_taxonomias.buscar_por_codigo(CODIGO_TAXONOMIA_PADRAO)
    taxonomia_criada = False
    if taxonomia is None:
        taxonomia = repo_taxonomias.salvar(criar_taxonomia_inicial())
        taxonomia_criada = True

    perfil = repo_perfis.buscar_por_codigo_e_versao(CODIGO_PERFIL_PADRAO, VERSAO_PERFIL_PADRAO)
    perfil_criado = False
    if perfil is None:
        perfil = repo_perfis.salvar(criar_perfil_inicial())
        perfil_criado = True

    return ResultadoSeed(
        taxonomia=taxonomia,
        perfil=perfil,
        taxonomia_criada=taxonomia_criada,
        perfil_criado=perfil_criado,
    )
