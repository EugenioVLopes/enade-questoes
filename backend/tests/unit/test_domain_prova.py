from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.enums import (
    CodigoAlertaExtracao,
    LetraAlternativa,
    OrigemAtivoVisual,
    SeveridadeAlerta,
    SituacaoGabarito,
    StatusAlerta,
    StatusIngestao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova import (
    AlertaExtracao,
    Alternativa,
    AtivoVisual,
    BoundingBox,
    FaixaQuestoes,
    Gabarito,
    Ingestao,
    MetadadosIngestao,
    Prova,
    Questao,
)


def _alternativas_completas() -> list[Alternativa]:
    return [Alternativa(letra=letra, texto=f"Texto da alternativa {letra.value}") for letra in LetraAlternativa]


def test_prova_valida_gera_chave_natural_e_faixa_padrao() -> None:
    prova = Prova(exame=" enade ", curso="Engenharia de Computação", ano=2023)
    assert prova.chave_natural == ("ENADE", "Engenharia de Computação", 2023)
    assert prova.faixa_ce == FaixaQuestoes(inicio=10, fim=38)


@pytest.mark.parametrize(
    ("exame", "curso", "ano"),
    [
        ("", "Engenharia de Computação", 2023),
        ("ENADE", "   ", 2023),
        ("ENADE", "Engenharia de Computação", 1800),
    ],
)
def test_prova_rejeita_campos_invalidos(exame: str, curso: str, ano: int) -> None:
    with pytest.raises(ErroValidacaoDominio):
        Prova(exame=exame, curso=curso, ano=ano, faixa_ce=FaixaQuestoes(10, 38))


def test_faixa_questoes_valida_limites_e_pertinencia() -> None:
    faixa = FaixaQuestoes(inicio=9, fim=35)
    assert faixa.contem(9) is True
    assert faixa.contem(35) is True
    assert faixa.contem(8) is False
    assert len(faixa) == 27
    assert list(faixa.numeros())[0] == 9

    with pytest.raises(ErroValidacaoDominio):
        FaixaQuestoes(inicio=0, fim=10)
    with pytest.raises(ErroValidacaoDominio):
        FaixaQuestoes(inicio=15, fim=10)


def test_bounding_box_rejeita_coordenadas_degeneradas_ou_nao_finitas() -> None:
    bbox = BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=200.0)
    assert bbox.x1 > bbox.x0

    with pytest.raises(ErroValidacaoDominio):
        BoundingBox(x0=10.0, y0=20.0, x1=10.0, y1=200.0)
    with pytest.raises(ErroValidacaoDominio):
        BoundingBox(x0=10.0, y0=50.0, x1=100.0, y1=20.0)
    with pytest.raises(ErroValidacaoDominio):
        BoundingBox(x0=0.0, y0=0.0, x1=float("nan"), y1=10.0)


def test_gabarito_respeita_invariantes_por_situacao() -> None:
    g_valido = Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)
    assert g_valido.alternativa_correta == LetraAlternativa.C
    assert Gabarito(SituacaoGabarito.ANULADA).alternativa_correta is None
    assert Gabarito(SituacaoGabarito.PENDENTE).alternativa_correta is None

    with pytest.raises(ErroValidacaoDominio):
        Gabarito(SituacaoGabarito.VALIDA, None)
    with pytest.raises(ErroValidacaoDominio):
        Gabarito(SituacaoGabarito.ANULADA, LetraAlternativa.A)
    with pytest.raises(ErroValidacaoDominio):
        Gabarito(SituacaoGabarito.PENDENTE, LetraAlternativa.B)


def test_ingestao_transicoes_de_estado_validas_e_invalidas() -> None:
    agora = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    ingestao = Ingestao(prova_id=uuid4())
    assert ingestao.status == StatusIngestao.PENDENTE

    with pytest.raises(ErroInvarianteDominio):
        ingestao.concluir(agora, MetadadosIngestao())

    ingestao.iniciar(agora)
    assert ingestao.status == StatusIngestao.PROCESSANDO

    ingestao.interromper(agora, "Reinício do worker")
    assert ingestao.status == StatusIngestao.INTERROMPIDA

    ingestao.iniciar(agora)
    ingestao.falhar("PDF corrompido", agora)
    assert ingestao.status == StatusIngestao.ERRO
    assert ingestao.mensagem_erro == "PDF corrompido"

    ingestao.iniciar(agora)
    ingestao.concluir(agora, MetadadosIngestao(total_questoes_extraidas=29, usou_ocr=False))
    assert ingestao.status == StatusIngestao.CONCLUIDA
    assert ingestao.metadados.total_questoes_extraidas == 29


def test_ativo_visual_permite_upload_manual_sem_pagina_e_exige_pagina_na_extracao() -> None:
    manual = AtivoVisual(origem=OrigemAtivoVisual.UPLOAD_MANUAL, alternativa_letra=LetraAlternativa.B)
    assert manual.pagina is None
    assert manual.bbox is None

    extraido = AtivoVisual(
        origem=OrigemAtivoVisual.FORMULA_RECORTE,
        pagina=12,
        bbox=BoundingBox(10.0, 20.0, 50.0, 40.0),
    )
    assert extraido.pagina == 12

    with pytest.raises(ErroValidacaoDominio):
        AtivoVisual(origem=OrigemAtivoVisual.PICTURE_DOCLING, pagina=None)
    with pytest.raises(ErroValidacaoDominio):
        AtivoVisual(origem=OrigemAtivoVisual.FORMULA_RECORTE, pagina=None)
    with pytest.raises(ErroValidacaoDominio):
        AtivoVisual(origem=OrigemAtivoVisual.UPLOAD_MANUAL, ordem=-1)


def test_alerta_extracao_valida_severidade_e_ciclo_resolvido() -> None:
    agora = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
    alerta = AlertaExtracao(codigo=CodigoAlertaExtracao.PDF_VIA_OCR, mensagem="OCR")
    assert alerta.severidade == SeveridadeAlerta.CRITICO
    assert alerta.is_critico is True
    assert alerta.is_inspecao is True

    alerta.resolver(agora)
    assert alerta.status == StatusAlerta.RESOLVIDO
    assert alerta.resolvido_em == agora

    alerta.reabrir("Reaberto")
    assert alerta.status == StatusAlerta.ABERTO
    assert alerta.resolvido_em is None

    with pytest.raises(ErroValidacaoDominio):
        AlertaExtracao(
            codigo=CodigoAlertaExtracao.PDF_VIA_OCR,
            severidade=SeveridadeAlerta.INFORMATIVO,
        )
    with pytest.raises(ErroInvarianteDominio):
        AlertaExtracao(
            codigo=CodigoAlertaExtracao.PDF_VIA_OCR,
            status=StatusAlerta.RESOLVIDO,
            resolvido_em=None,
        )
    with pytest.raises(ErroValidacaoDominio):
        alerta.resolver(None)  # type: ignore[arg-type]
    with pytest.raises(ErroValidacaoDominio):
        AlertaExtracao(
            codigo=CodigoAlertaExtracao.PDF_VIA_OCR,
            status=StatusAlerta.RESOLVIDO,
            resolvido_em="2026-11-20T00:00:00Z",  # type: ignore[arg-type]
        )


def test_questao_rejeita_numero_invalido_e_alternativas_duplicadas() -> None:
    prova_id = uuid4()
    questao = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Considere um grafo direcionado acíclico com V vértices.",
        paginas=(5, 6),
        alternativas=_alternativas_completas(),
    )
    assert questao.tem_alerta_critico_aberto is False

    questao.aplicar_gabarito_oficial(Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A))
    assert questao.editada_manualmente is False

    questao.editar_conteudo(enunciado="Enunciado revisado manualmente com detalhamento.")
    assert questao.editada_manualmente is True

    with pytest.raises(ErroValidacaoDominio):
        Questao(prova_id=prova_id, numero=0, enunciado="Texto válido")

    with pytest.raises(ErroValidacaoDominio):
        Questao(
            prova_id=prova_id,
            numero=11,
            enunciado="Texto válido",
            alternativas=[
                Alternativa(LetraAlternativa.A, "1"),
                Alternativa(LetraAlternativa.A, "2"),
            ],
        )


def test_questao_faz_copia_defensiva_das_listas_recebidas_e_rejeita_tipos_invalidos() -> None:
    prova_id = uuid4()
    alts = _alternativas_completas()
    ativos = [AtivoVisual(origem=OrigemAtivoVisual.UPLOAD_MANUAL)]
    alertas = [AlertaExtracao(codigo=CodigoAlertaExtracao.PDF_VIA_OCR)]

    questao = Questao(
        prova_id=prova_id,
        numero=12,
        enunciado="Enunciado com listas copiadas defensivamente.",
        alternativas=alts,
        ativos_visuais=ativos,
        alertas_extracao=alertas,
    )

    alts.append(Alternativa(LetraAlternativa.A, "Duplicada externa"))
    ativos.clear()
    alertas.append(AlertaExtracao(codigo=CodigoAlertaExtracao.ENUNCIADO_SUSPEITO))

    assert len(questao.alternativas) == 5
    assert len(questao.ativos_visuais) == 1
    assert len(questao.alertas_extracao) == 1

    with pytest.raises(ErroValidacaoDominio):
        Questao(
            prova_id=prova_id,
            numero=13,
            enunciado="Enunciado válido.",
            alternativas="ABCDE",  # type: ignore[arg-type]
        )
    with pytest.raises(ErroValidacaoDominio):
        Questao(
            prova_id=prova_id,
            numero=14,
            enunciado="Enunciado válido.",
            ativos_visuais={"a": 1},  # type: ignore[arg-type]
        )
    with pytest.raises(ErroValidacaoDominio):
        Questao(
            prova_id=prova_id,
            numero=15,
            enunciado="Enunciado válido.",
            alertas_extracao=b"ocr",  # type: ignore[arg-type]
        )
    with pytest.raises(ErroValidacaoDominio):
        Questao(
            prova_id=prova_id,
            numero=16,
            enunciado="Enunciado válido.",
            alternativas=memoryview(b"ABCDE"),  # type: ignore[arg-type]
        )
    with pytest.raises(ErroValidacaoDominio):
        questao.editar_conteudo(alternativas=memoryview(b"ABCDE"))  # type: ignore[arg-type]
    assert questao.editada_manualmente is False
