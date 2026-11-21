"""Testes de integração do cache determinístico em disco (DATA_DIR/cache/llm/{sha256}.json, sem rede)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from application.classificacao import ClassificarQuestaoService
from application.seed import criar_perfil_inicial
from domain.classificacao import PerfilClassificacao
from domain.enums import ComponenteProva, LetraAlternativa, OrigemAtivoVisual
from domain.prova import Alternativa, AtivoVisual, Questao
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.llm.cliente_openai import ClienteOpenAICompativel
from infrastructure.storage.local import ArmazenamentoArquivosLocal


class _FakeCompletions:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls: int = 0

    def create(self, **kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self._payload)))],
            usage=SimpleNamespace(prompt_tokens=210, completion_tokens=55),
            model=f"{kwargs['model']}-efetivo",
        )


def _criar_adaptador(
    data_dir: Path,
    *,
    provider: str = "gemini_openai",
    model: str = "gemini-2.5-flash-lite",
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
) -> tuple[ClienteOpenAICompativel, ArmazenamentoArquivosLocal, _FakeCompletions]:
    payload = {
        "disciplina_principal": "algoritmos-e-estruturas-de-dados",
        "disciplinas_secundarias": ["redes-e-comunicacoes"],
        "topicos": ["grafos", "bfs"],
        "justificativa": "Questão clássica de busca em grafos.",
        "confianca": 0.94,
    }
    completions = _FakeCompletions(payload)
    fake_openai = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    armazenamento = ArmazenamentoArquivosLocal(data_dir)
    adaptador = ClienteOpenAICompativel(
        provider=provider,
        base_url=base_url,
        api_key="fake-key",
        model=model,
        max_rpm=0,
        armazenamento=armazenamento,
        client=fake_openai,
    )
    return adaptador, armazenamento, completions


def _taxonomia_base() -> Taxonomia:
    return Taxonomia(
        codigo="enade-ec",
        nome="ENADE Engenharia de Computação",
        curso_referencia="Engenharia de Computação",
        disciplinas=[
            Disciplina("algoritmos-e-estruturas-de-dados", "Algoritmos", "Estruturas e grafos", ativa=True),
            Disciplina("redes-e-comunicacoes", "Redes", "Camadas e roteamento", ativa=True),
        ],
    )


def _questao_base(
    *,
    enunciado: str = "Qual a complexidade da busca em largura em um grafo G=(V,E)?",
    alt_a: str = "O(|V| + |E|)",
    chave_img: str = "provas/p1/q1.png",
) -> Questao:
    return Questao(
        prova_id=uuid4(),
        numero=1,
        enunciado=enunciado,
        componente=ComponenteProva.COMPONENTE_ESPECIFICO,
        alternativas=[
            Alternativa(LetraAlternativa.A, alt_a),
            Alternativa(LetraAlternativa.B, "O(|V|^2)"),
        ],
        ativos_visuais=[
            AtivoVisual(
                origem=OrigemAtivoVisual.PICTURE_DOCLING,
                ordem=0,
                pagina=2,
                chave_arquivo=chave_img,
            )
        ],
    )


def test_cache_em_disco_persiste_reaproveita_e_respeita_ignorar_cache(tmp_path: Path) -> None:
    adaptador, armazenamento, completions = _criar_adaptador(tmp_path)
    armazenamento.salvar("provas/p1/q1.png", b"\x89PNG-IMAGEM-1")

    servico = ClassificarQuestaoService(adaptador, armazenamento=armazenamento)
    taxonomia = _taxonomia_base()
    perfil = criar_perfil_inicial()
    questao = _questao_base()

    # 1a chamada: cache miss -> chama cliente mockado e grava DATA_DIR/cache/llm/{sha256}.json
    res1 = servico.classificar(questao=questao, taxonomia=taxonomia, perfil=perfil)
    assert res1.sucesso is True
    assert completions.calls == 1
    assert res1.metricas.cache_hit is False
    assert res1.metricas.prompt_tokens == 210
    assert res1.metricas.completion_tokens == 55
    assert res1.metricas.latencia_ms >= 0.0
    assert res1.metricas.modo_schema == "json_schema"
    assert res1.metricas.tentativas == 1
    assert res1.metricas.modelo_efetivo == "gemini-2.5-flash-lite-efetivo"

    arquivo_cache = tmp_path / "cache" / "llm" / f"{res1.metricas.cache_key}.json"
    assert arquivo_cache.is_file()
    conteudo_disco = json.loads(arquivo_cache.read_text(encoding="utf-8"))
    assert conteudo_disco["cache_key"] == res1.metricas.cache_key
    assert conteudo_disco["dados_brutos"]["disciplina_principal"] == "algoritmos-e-estruturas-de-dados"

    # 2a chamada idêntica: cache hit -> zero chamadas ao cliente OpenAI
    res2 = servico.classificar(questao=questao, taxonomia=taxonomia, perfil=perfil)
    assert res2.sucesso is True
    assert completions.calls == 1
    assert res2.metricas.cache_hit is True
    assert res2.metricas.cache_key == res1.metricas.cache_key
    assert res2.metricas.prompt_tokens == 210
    assert res2.metricas.completion_tokens == 55
    assert res2.metricas.modo_schema == "json_schema"

    # 3a chamada com ignorar_cache=True: força chamada ao cliente mesmo existindo cache
    res3 = servico.classificar(questao=questao, taxonomia=taxonomia, perfil=perfil, ignorar_cache=True)
    assert res3.sucesso is True
    assert completions.calls == 2
    assert res3.metricas.cache_hit is False
    assert res3.metricas.cache_key == res1.metricas.cache_key


def test_chave_cache_muda_para_toda_dimensao_de_entrada(tmp_path: Path) -> None:
    adaptador, armazenamento, _ = _criar_adaptador(tmp_path)
    armazenamento.salvar("provas/p1/q1.png", b"\x89PNG-A")
    armazenamento.salvar("provas/p1/q1_mod.png", b"\x89PNG-B")

    servico = ClassificarQuestaoService(adaptador, armazenamento=armazenamento)
    taxonomia = _taxonomia_base()
    perfil = criar_perfil_inicial()
    questao = _questao_base()

    base_key = servico.classificar(questao=questao, taxonomia=taxonomia, perfil=perfil).metricas.cache_key

    # 1. Enunciado alterado
    k_enunciado = servico.classificar(
        questao=_questao_base(enunciado="Enunciado diferente sobre DFS."),
        taxonomia=taxonomia,
        perfil=perfil,
    ).metricas.cache_key
    assert k_enunciado != base_key

    # 2. Alternativa alterada
    k_alternativa = servico.classificar(
        questao=_questao_base(alt_a="O(|V| log |V|)"),
        taxonomia=taxonomia,
        perfil=perfil,
    ).metricas.cache_key
    assert k_alternativa != base_key

    # 3. Imagem alterada
    k_imagem = servico.classificar(
        questao=_questao_base(chave_img="provas/p1/q1_mod.png"),
        taxonomia=taxonomia,
        perfil=perfil,
    ).metricas.cache_key
    assert k_imagem != base_key

    # 4. Taxonomia alterada (ementa / nova disciplina)
    taxonomia_alterada = Taxonomia(
        codigo=taxonomia.codigo,
        nome=taxonomia.nome,
        curso_referencia=taxonomia.curso_referencia,
        disciplinas=[
            Disciplina("algoritmos-e-estruturas-de-dados", "Algoritmos", "Ementa atualizada", ativa=True),
            Disciplina("redes-e-comunicacoes", "Redes", "Camadas e roteamento", ativa=True),
        ],
    )
    k_taxonomia = servico.classificar(
        questao=questao,
        taxonomia=taxonomia_alterada,
        perfil=perfil,
    ).metricas.cache_key
    assert k_taxonomia != base_key

    # 5. Perfil de Classificação alterado (versão ou diretrizes)
    perfil_alterado = replace(perfil, versao="v2")
    k_perfil = servico.classificar(
        questao=questao,
        taxonomia=taxonomia,
        perfil=perfil_alterado,
    ).metricas.cache_key
    assert k_perfil != base_key

    # 6. Modelo / provedor alterado
    adaptador_outro_modelo, _, _ = _criar_adaptador(tmp_path, model="gemini-2.5-pro")
    servico_outro_modelo = ClassificarQuestaoService(adaptador_outro_modelo, armazenamento=armazenamento)
    k_modelo = servico_outro_modelo.classificar(
        questao=questao,
        taxonomia=taxonomia,
        perfil=perfil,
    ).metricas.cache_key
    assert k_modelo != base_key

    # Todas as 7 chaves distintas entre si
    assert len({base_key, k_enunciado, k_alternativa, k_imagem, k_taxonomia, k_perfil, k_modelo}) == 7


def test_cache_key_invalida_em_template_customizado_fixo_e_reaproveita_instancias_equivalentes(
    tmp_path: Path,
) -> None:
    adaptador, armazenamento, completions = _criar_adaptador(tmp_path)
    armazenamento.salvar("provas/p1/q1.png", b"\x89PNG-A")
    servico = ClassificarQuestaoService(adaptador, armazenamento=armazenamento)
    questao = _questao_base()

    def _criar_taxonomia_custom(
        *,
        nome: str = "ENADE Engenharia de Computação",
        curso: str = "Engenharia de Computação",
        ementa_alg: str = "Estruturas e grafos",
        ativa_so: bool = False,
    ) -> Taxonomia:
        return Taxonomia(
            codigo="enade-ec",
            nome=nome,
            curso_referencia=curso,
            disciplinas=[
                Disciplina("algoritmos-e-estruturas-de-dados", "Algoritmos", ementa_alg, ativa=True),
                Disciplina("redes-e-comunicacoes", "Redes", "Camadas e roteamento", ativa=True),
                Disciplina("sistemas-operacionais", "SO", "Processos e memória", ativa=ativa_so),
            ],
        )

    def _criar_perfil_custom(
        *,
        diretrizes: str = "Diretriz v1",
        fronteiras: str = "Fronteira v1",
        descricao: str = "Desc v1",
    ) -> PerfilClassificacao:
        return PerfilClassificacao(
            codigo="fixo",
            versao="v1",
            descricao=descricao,
            diretrizes_gerais=diretrizes,
            guia_fronteiras=fronteiras,
            template_prompt="[SYSTEM]\nFixo\n[USER]\n{enunciado}",
        )

    res_base = servico.classificar(
        questao=questao,
        taxonomia=_criar_taxonomia_custom(),
        perfil=_criar_perfil_custom(),
    )
    base_key = res_base.metricas.cache_key
    assert completions.calls == 1
    assert res_base.metricas.cache_hit is False

    # Instâncias reconstruídas (UUIDs diferentes, conteúdo idêntico) devem acertar o cache
    res_hit = servico.classificar(
        questao=questao,
        taxonomia=_criar_taxonomia_custom(),
        perfil=_criar_perfil_custom(),
    )
    assert res_hit.metricas.cache_hit is True
    assert res_hit.metricas.cache_key == base_key
    assert completions.calls == 1

    # Alterações em Perfil e Taxonomia não presentes no template fixo DEVEM invalidar o cache
    mutacoes = [
        (_criar_taxonomia_custom(), _criar_perfil_custom(diretrizes="Diretriz v2")),
        (_criar_taxonomia_custom(), _criar_perfil_custom(fronteiras="Fronteira v2")),
        (_criar_taxonomia_custom(), _criar_perfil_custom(descricao="Desc v2")),
        (_criar_taxonomia_custom(ementa_alg="Ementa modificada"), _criar_perfil_custom()),
        (_criar_taxonomia_custom(ativa_so=True), _criar_perfil_custom()),
        (_criar_taxonomia_custom(nome="Outro Nome"), _criar_perfil_custom()),
        (_criar_taxonomia_custom(curso="Outro Curso"), _criar_perfil_custom()),
    ]
    chaves = {base_key}
    for idx, (tax_mut, perf_mut) in enumerate(mutacoes, start=2):
        res_mut = servico.classificar(questao=questao, taxonomia=tax_mut, perfil=perf_mut)
        assert res_mut.metricas.cache_hit is False
        assert completions.calls == idx
        chaves.add(res_mut.metricas.cache_key)

    assert len(chaves) == 8
