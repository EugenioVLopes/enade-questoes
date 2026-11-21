from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.avaliacao import ChaveQuestaoOuro, ConjuntoOuro, ItemConjuntoOuro
from domain.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    ExecucaoClassificacao,
    PerfilClassificacao,
)
from domain.enums import (
    CodigoAlertaExtracao,
    OrigemClassificacao,
    ResolucaoDivergencia,
    SituacaoGabarito,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova import AlertaExtracao
from domain.taxonomia import Disciplina, Taxonomia, Topico, normalizar_topico


def _taxonomia_exemplo() -> Taxonomia:
    return Taxonomia(
        codigo="enade-ec-v1",
        nome="Matriz ENADE Eng. Computação",
        curso_referencia="Engenharia de Computação",
        disciplinas=[
            Disciplina(codigo="algoritmos", nome="Algoritmos", ementa="Complexidade e grafos."),
            Disciplina(codigo="redes", nome="Redes", ementa="Protocolos TCP/IP."),
            Disciplina(codigo="legado", nome="Disciplina Legada", ementa="Antiga.", ativa=False),
        ],
    )


def test_taxonomia_filtra_ativas_e_gera_snapshot_sem_arquivadas() -> None:
    taxonomia = _taxonomia_exemplo()
    assert [d.codigo for d in taxonomia.ativas()] == ["algoritmos", "redes"]
    assert set(taxonomia.mapa_ativas()) == {"algoritmos", "redes"}
    snapshot = taxonomia.snapshot_dict()
    assert [d["codigo"] for d in snapshot["disciplinas"]] == ["algoritmos", "redes"]

    with pytest.raises(ErroValidacaoDominio):
        Taxonomia(
            codigo="dup",
            nome="Dup",
            disciplinas=[
                Disciplina(codigo="algoritmos", nome="A1"),
                Disciplina(codigo="algoritmos", nome="A2"),
            ],
        )


def test_topico_normalizacao_ascii_kebab_sem_cortar_palavras() -> None:
    assert normalizar_topico("Computação Gráfica") == "computacao-grafica"
    assert normalizar_topico("TCP / UDP!!") == "tcp-udp"
    resultado = normalizar_topico("processamento-digital-de-sinais-avancados")
    assert resultado == "processamento-digital-de-sinais"
    assert len(resultado) == 31
    assert normalizar_topico("tokenunicocommaisdetrintaedoiscaracteres") == ""
    assert Topico.criar("Árvores Binárias").valor == "arvores-binarias"

    with pytest.raises(ErroValidacaoDominio):
        Topico("!!!")


def test_execucao_classificacao_congela_snapshots_e_transiciona_estados() -> None:
    taxonomia = _taxonomia_exemplo()
    perfil = PerfilClassificacao(
        codigo="v2-fronteiras",
        versao="2.0.0",
        diretrizes_gerais="Classifique pelo núcleo técnico cobrado.",
        guia_fronteiras="Algoritmos vs Redes.",
        template_prompt="Analise a questão.",
    )
    snap_tax = taxonomia.snapshot_dict()
    snap_perf = perfil.snapshot_dict()

    execucao = ExecucaoClassificacao(
        taxonomia_id=taxonomia.id,
        perfil_id=perfil.id,
        snapshot_taxonomia=snap_tax,
        snapshot_perfil=snap_perf,
    )
    snap_tax["codigo"] = "mutado-externamente"
    assert execucao.snapshot_taxonomia["codigo"] == "enade-ec-v1"

    with pytest.raises(TypeError):
        execucao.snapshot_taxonomia["codigo"] = "tentativa"  # type: ignore[index]

    execucao_com_sets = ExecucaoClassificacao(
        taxonomia_id=taxonomia.id,
        perfil_id=perfil.id,
        snapshot_taxonomia={**snap_tax, "tags": {"a", "b"}},
        snapshot_perfil=snap_perf,
    )
    assert isinstance(execucao_com_sets.snapshot_taxonomia["tags"], frozenset)

    agora = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    execucao.iniciar(agora, total_itens=10)
    assert execucao.status == StatusExecucaoClassificacao.PROCESSANDO
    execucao.concluir(agora)
    assert execucao.status == StatusExecucaoClassificacao.CONCLUIDA


def test_classificacao_aprovar_in_place_e_corrigir_append_only() -> None:
    agora = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    ia = Classificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        disciplina_principal="algoritmos",
        disciplinas_secundarias=("redes",),
        topicos=("grafos",),
        justificativa="Caminhos mínimos.",
        confianca=0.92,
        origem=OrigemClassificacao.AUTOMATICA,
        status=StatusClassificacao.PENDENTE_REVISAO,
    )
    ia.aprovar(agora)
    assert ia.status == StatusClassificacao.APROVADA
    assert ia.origem == OrigemClassificacao.AUTOMATICA
    assert ia.vigente is True

    humana = ia.substituir_por_correcao(
        disciplina_principal="redes",
        disciplinas_secundarias=("algoritmos",),
        topicos=("Roteamento OSPF",),
        justificativa="Foco no protocolo OSPF.",
        agora=agora,
    )
    assert ia.vigente is False
    assert ia.disciplina_principal == "algoritmos"
    assert humana.vigente is True
    assert humana.origem == OrigemClassificacao.HUMANA
    assert humana.status == StatusClassificacao.APROVADA
    assert humana.substitui_classificacao_id == ia.id
    assert humana.topicos == ("roteamento-ospf",)

    with pytest.raises(ErroInvarianteDominio):
        ia.aprovar(agora)


def test_divergencia_reclassificacao_resolve_apenas_uma_vez() -> None:
    agora = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    div = DivergenciaReclassificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        execucao_id=uuid4(),
        classificacao_vigente_id=uuid4(),
        disciplina_principal_candidata="redes",
        confianca_candidata=0.88,
    )
    assert div.status == StatusDivergencia.ABERTA
    div.resolver(ResolucaoDivergencia.MANTER_HUMANA, agora)
    assert div.status == StatusDivergencia.RESOLVIDA
    assert div.resolucao == ResolucaoDivergencia.MANTER_HUMANA

    with pytest.raises(ErroInvarianteDominio):
        div.resolver(ResolucaoDivergencia.ACEITAR_CANDIDATA, agora)

    div_aberta = DivergenciaReclassificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        execucao_id=uuid4(),
        classificacao_vigente_id=uuid4(),
        disciplina_principal_candidata="redes",
        confianca_candidata=0.88,
    )
    with pytest.raises(ErroValidacaoDominio):
        div_aberta.resolver(ResolucaoDivergencia.MANTER_HUMANA, None)  # type: ignore[arg-type]


def test_conjunto_ouro_ordena_por_chave_natural_e_valida_preflight() -> None:
    agora = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    taxonomia = _taxonomia_exemplo()
    chave_23_15 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 15)
    chave_19_10 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2019, 10)

    conjunto = ConjuntoOuro(
        versao_schema="1.0",
        taxonomia_codigo="enade-ec-v1",
        exportado_em=agora,
        itens=(
            ItemConjuntoOuro(chave=chave_23_15, disciplina_principal="algoritmos"),
            ItemConjuntoOuro(
                chave=chave_19_10,
                disciplina_principal="redes",
                situacao_gabarito=SituacaoGabarito.ANULADA,
            ),
        ),
    )
    assert [item.chave for item in conjunto.itens] == [chave_19_10, chave_23_15]

    erros_ok = conjunto.validar_preflight(taxonomia, {chave_19_10: (), chave_23_15: ()})
    assert erros_ok == []

    erros_falha = conjunto.validar_preflight(
        taxonomia,
        {
            chave_19_10: (AlertaExtracao(codigo=CodigoAlertaExtracao.PDF_VIA_OCR),),
        },
    )
    assert len(erros_falha) == 2

    aprovada = Classificacao(
        questao_id=uuid4(),
        taxonomia_id=taxonomia.id,
        disciplina_principal="algoritmos",
        status=StatusClassificacao.APROVADA,
        vigente=True,
    )
    assert ConjuntoOuro.item_elegivel(aprovada, ()) is True
    assert (
        ConjuntoOuro.item_elegivel(
            aprovada,
            (AlertaExtracao(codigo=CodigoAlertaExtracao.ENUNCIADO_SUSPEITO),),
        )
        is False
    )


def test_classificacao_substituir_por_correcao_preserva_vigente_em_erro_e_permite_retry() -> None:
    agora = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)
    atual = Classificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        disciplina_principal="algoritmos",
        disciplinas_secundarias=("redes",),
        justificativa="Inicial.",
        confianca=0.9,
    )

    with pytest.raises(ErroValidacaoDominio):
        atual.substituir_por_correcao(
            disciplina_principal="algoritmos",
            disciplinas_secundarias=("algoritmos",),
            justificativa="Secundária igual à principal.",
            agora=agora,
        )
    assert atual.vigente is True

    with pytest.raises(ErroValidacaoDominio):
        atual.substituir_por_correcao(
            disciplina_principal="algoritmos",
            disciplinas_secundarias="redes",  # type: ignore[arg-type]
            justificativa="Secundária passada como string.",
            agora=agora,
        )
    assert atual.vigente is True

    corrigida = atual.substituir_por_correcao(
        disciplina_principal="redes",
        disciplinas_secundarias=("algoritmos",),
        justificativa="Correção válida após erro.",
        agora=agora,
    )
    assert atual.vigente is False
    assert corrigida.vigente is True
    assert corrigida.substitui_classificacao_id == atual.id


@pytest.mark.parametrize(
    "secundarias_invalidas",
    ["ia", b"ia", bytearray(b"ia"), memoryview(b"ia"), {"redes": 1}, 123, [123]],
)
def test_entidades_rejeitam_disciplinas_secundarias_nao_iteraveis_ou_string_mapping(
    secundarias_invalidas: object,
) -> None:
    with pytest.raises(ErroValidacaoDominio):
        Classificacao(
            questao_id=uuid4(),
            taxonomia_id=uuid4(),
            disciplina_principal="algoritmos",
            disciplinas_secundarias=secundarias_invalidas,  # type: ignore[arg-type]
        )

    with pytest.raises(ErroValidacaoDominio):
        DivergenciaReclassificacao(
            questao_id=uuid4(),
            taxonomia_id=uuid4(),
            execucao_id=uuid4(),
            classificacao_vigente_id=uuid4(),
            disciplina_principal_candidata="redes",
            disciplinas_secundarias_candidatas=secundarias_invalidas,  # type: ignore[arg-type]
        )

    with pytest.raises(ErroValidacaoDominio):
        ItemConjuntoOuro(
            chave=ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 10),
            disciplina_principal="algoritmos",
            disciplinas_secundarias=secundarias_invalidas,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "colecao_invalida",
    ["grafos", b"grafos", bytearray(b"grafos"), memoryview(b"grafos"), {"grafos": 1}, 123, [123], ["grafos", 123]],
)
def test_entidades_classificacao_rejeitam_topicos_e_alertas_invalidos(colecao_invalida: object) -> None:
    agora = datetime(2026, 11, 20, 23, 0, tzinfo=UTC)
    with pytest.raises(ErroValidacaoDominio):
        Classificacao(
            questao_id=uuid4(),
            taxonomia_id=uuid4(),
            disciplina_principal="algoritmos",
            topicos=colecao_invalida,  # type: ignore[arg-type]
        )

    with pytest.raises(ErroValidacaoDominio):
        Classificacao(
            questao_id=uuid4(),
            taxonomia_id=uuid4(),
            disciplina_principal="algoritmos",
            alertas_validacao=colecao_invalida,  # type: ignore[arg-type]
        )

    with pytest.raises(ErroValidacaoDominio):
        DivergenciaReclassificacao(
            questao_id=uuid4(),
            taxonomia_id=uuid4(),
            execucao_id=uuid4(),
            classificacao_vigente_id=uuid4(),
            disciplina_principal_candidata="redes",
            topicos_candidatos=colecao_invalida,  # type: ignore[arg-type]
        )

    atual = Classificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        disciplina_principal="algoritmos",
        topicos=("grafos",),
    )
    with pytest.raises(ErroValidacaoDominio):
        atual.substituir_por_correcao(
            disciplina_principal="redes",
            topicos=colecao_invalida,  # type: ignore[arg-type]
            justificativa="Correção com tópico inválido.",
            agora=agora,
        )
    assert atual.vigente is True


def test_taxonomia_e_conjunto_ouro_materializam_geradores_e_rejeitam_entradas_invalidas() -> None:
    agora = datetime(2026, 11, 20, 23, 0, tzinfo=UTC)
    tax = Taxonomia(
        codigo="cc-2026",
        nome="Ciência da Computação",
        disciplinas=(d for d in [Disciplina("algoritmos", "Algoritmos"), Disciplina("redes", "Redes")]),  # type: ignore[arg-type]
    )
    assert [d.codigo for d in tax.ativas()] == ["algoritmos", "redes"]
    assert set(tax.mapa_todas()) == {"algoritmos", "redes"}

    chave_23_15 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, 15)
    chave_19_10 = ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2019, 10)
    conjunto = ConjuntoOuro(
        versao_schema="1.0",
        taxonomia_codigo="cc-2026",
        exportado_em=agora,
        itens=(  # type: ignore[arg-type]
            x
            for x in [
                ItemConjuntoOuro(chave=chave_23_15, disciplina_principal="algoritmos"),
                ItemConjuntoOuro(chave=chave_19_10, disciplina_principal="redes"),
            ]
        ),
    )
    assert conjunto.total_itens == 2
    assert [item.chave for item in conjunto.itens] == [chave_19_10, chave_23_15]

    for invalido in ("algoritmos", b"alg", bytearray(b"alg"), memoryview(b"alg"), {"a": 1}, 123, ["algoritmos"]):
        with pytest.raises(ErroValidacaoDominio):
            Taxonomia(codigo="cc-2026", nome="CC", disciplinas=invalido)  # type: ignore[arg-type]
        with pytest.raises(ErroValidacaoDominio):
            ConjuntoOuro(versao_schema="1.0", taxonomia_codigo="cc-2026", exportado_em=agora, itens=invalido)  # type: ignore[arg-type]

    atual = Classificacao(
        questao_id=uuid4(),
        taxonomia_id=tax.id,
        disciplina_principal="algoritmos",
        topicos=(t for t in ["grafos"]),  # type: ignore[arg-type]
        alertas_validacao=(a for a in ["baixa_confianca"]),  # type: ignore[arg-type]
    )
    assert atual.topicos == ("grafos",)
    assert atual.alertas_validacao == ("baixa_confianca",)

    corrigida = atual.substituir_por_correcao(
        disciplina_principal="redes",
        topicos=(t for t in ["Roteamento OSPF", "OSPF"]),
        justificativa="Correção via gerador.",
        agora=agora,
    )
    assert corrigida.topicos == ("roteamento-ospf", "ospf")

    div = DivergenciaReclassificacao(
        questao_id=uuid4(),
        taxonomia_id=tax.id,
        execucao_id=uuid4(),
        classificacao_vigente_id=atual.id,
        disciplina_principal_candidata="redes",
        topicos_candidatos=(t for t in ["roteamento"]),  # type: ignore[arg-type]
    )
    assert div.topicos_candidatos == ("roteamento",)
