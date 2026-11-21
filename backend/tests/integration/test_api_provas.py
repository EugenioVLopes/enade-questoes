"""Testes de integração dos endpoints /api/v1/provas e /api/v1/ativos-visuais."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session, sessionmaker

from application.ports.extracao import (
    AlternativaExtraida,
    AtivoVisualExtraido,
    ItemGabaritoExtraido,
    QuestaoExtraida,
    ResultadoExtracaoGabarito,
    ResultadoExtracaoProva,
)
from domain.classificacao import Classificacao
from domain.enums import (
    CodigoAlertaExtracao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    SituacaoGabarito,
    StatusClassificacao,
    StatusIngestao,
    TipoQuestao,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova import BoundingBox, FaixaQuestoes, Gabarito, Ingestao, MetadadosIngestao
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.config import Settings
from infrastructure.extracao import (
    ExtratorGabaritoPdfPlumber,
    ExtratorProvaDocling,
    RenderizadorPaginaPdfPypdfium2,
)
from infrastructure.persistence.repositorios import (
    RepositorioClassificacoesSqlAlchemy,
    RepositorioIngestoesSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from presentation.main import build_app

REPO_ROOT = Path(__file__).resolve().parents[3]
PROVA_2023_REAL = REPO_ROOT / "data" / "enade" / "2023" / "prova_enade_2023_engenharia_computacao.pdf"
GAB_2023_REAL = REPO_ROOT / "data" / "enade" / "2023" / "gabarito_enade_2023_engenharia_computacao.pdf"


def _gerar_png_bytes(cor: tuple[int, int, int] = (20, 90, 180)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (40, 24), color=cor).save(buf, format="PNG")
    return buf.getvalue()


def _gerar_pdf_bytes_valido(num_paginas: int = 2) -> bytes:
    doc = pdfium.PdfDocument.new()
    try:
        for _ in range(num_paginas):
            doc.new_page(width=200, height=280)
        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


class _FakeExtratorProvaRico:
    def __init__(self) -> None:
        self.versao = 1
        self.deve_falhar = False

    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva:
        if self.deve_falhar:
            raise RuntimeError("Erro simulado na extração da prova")

        png_q10 = _gerar_png_bytes((200, 30, 30) if self.versao == 1 else (30, 180, 60))
        png_q11 = _gerar_png_bytes((15, 60, 210) if self.versao == 1 else (220, 160, 20))
        alternativas_completas = tuple(
            AlternativaExtraida(letra=letra, texto=f"Texto v{self.versao} alternativa {letra.value}.")
            for letra in LetraAlternativa
        )
        questoes = (
            QuestaoExtraida(
                numero=10,
                enunciado=f"Questão 10 (v{self.versao}) sobre análise de complexidade de algoritmos.",
                paginas=(1,),
                alternativas=alternativas_completas,
                ativos_visuais=(
                    AtivoVisualExtraido(
                        origem=OrigemAtivoVisual.PICTURE_DOCLING,
                        conteudo_png=png_q10,
                        ordem=0,
                        pagina=1,
                        bbox=BoundingBox(10.0, 20.0, 100.0, 80.0),
                    ),
                ),
            ),
            QuestaoExtraida(
                numero=11,
                enunciado=f"Questão 11 (v{self.versao}) com figura e estrutura completa de alternativas.",
                paginas=(1, 2),
                alternativas=alternativas_completas,
                ativos_visuais=(
                    AtivoVisualExtraido(
                        origem=OrigemAtivoVisual.FORMULA_RECORTE,
                        conteudo_png=png_q11,
                        ordem=0,
                        pagina=2,
                        bbox=BoundingBox(15.0, 30.0, 90.0, 65.0),
                    ),
                ),
            ),
            QuestaoExtraida(
                numero=12,
                enunciado=f"Questão 12 (v{self.versao}) com alternativas incompletas para testar alerta crítico.",
                paginas=(2,),
                alternativas=alternativas_completas[:3],
                ativos_visuais=(),
            ),
        )
        return ResultadoExtracaoProva(
            questoes=questoes,
            extracao_bruta_json='{"pages": [1, 2]}',
            metadados=MetadadosIngestao(
                total_questoes_extraidas=len(questoes),
                imagens_detectadas=5,
                imagens_filtradas_margem=3,
                formulas_recortadas=1,
                usou_ocr=False,
                paginas_fonte_symbol=(2,),
            ),
        )


class _FakeExtratorGabaritoStateful:
    def __init__(self) -> None:
        self.itens_por_marcador: dict[bytes, tuple[ItemGabaritoExtraido, ...]] = {}
        self.padrao: tuple[ItemGabaritoExtraido, ...] = (
            ItemGabaritoExtraido(10, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A)),
            ItemGabaritoExtraido(11, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B)),
        )

    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito:
        conteudo = caminho_pdf.read_bytes()
        if b"INVALIDO" in conteudo:
            raise ErroValidacaoDominio("PDF de gabarito sem tabelas válidas.")
        for marcador, itens in self.itens_por_marcador.items():
            if marcador in conteudo:
                return ResultadoExtracaoGabarito(itens=itens)
        return ResultadoExtracaoGabarito(itens=self.padrao)


def test_ciclo_completo_provas_gabarito_reprocessamento_e_midia(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_classif = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    tax = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE Engenharia de Computação",
            curso_referencia="Engenharia de Computação",
            disciplinas=[
                Disciplina(codigo="algoritmos", nome="Algoritmos"),
                Disciplina(codigo="redes", nome="Redes"),
            ],
        )
    )

    extrator_prova = _FakeExtratorProvaRico()
    extrator_gab = _FakeExtratorGabaritoStateful()
    hook_chamadas: list[tuple[UUID, UUID, UUID | None]] = []
    exec_encadeada_id = uuid4()

    def _hook(*, prova_id: UUID, taxonomia_id: UUID, perfil_id: UUID | None) -> UUID | None:
        hook_chamadas.append((prova_id, taxonomia_id, perfil_id))
        return exec_encadeada_id

    data_dir = tmp_path / "app_data"
    pdf_prova_bytes = _gerar_pdf_bytes_valido(num_paginas=2)
    pdf_gab_inicial = b"%PDF-1.4 gabarito inicial"

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=data_dir),
        extrator_prova=extrator_prova,
        extrator_gabarito=extrator_gab,
        classificacao_hook=_hook,
    )

    with TestClient(app) as client:
        # 1. POST /api/v1/provas -> 202 Accepted
        resp_post = client.post(
            "/api/v1/provas",
            data={
                "exame": "ENADE",
                "curso": "Engenharia de Computação",
                "ano": "2023",
                "taxonomia_id": str(tax.id),
            },
            files={
                "arquivo_prova": ("prova_2023.pdf", pdf_prova_bytes, "application/pdf"),
                "arquivo_gabarito": ("gab_2023.pdf", pdf_gab_inicial, "application/pdf"),
            },
        )
        assert resp_post.status_code == 202
        body_post = resp_post.json()
        prova_id = UUID(body_post["prova_id"])
        assert body_post["status"] == "pendente"
        assert body_post["questao_inicio"] == 10
        assert body_post["questao_fim"] == 38
        assert body_post["possui_gabarito"] is True

        app.state.worker.aguardar_ocioso(timeout=10.0)

        # 2. Duplicidade (case-insensitive em exame) -> 409 Conflict com prova_id
        resp_dup = client.post(
            "/api/v1/provas",
            data={"exame": "enade", "curso": "Engenharia de Computação", "ano": "2023"},
            files={"arquivo_prova": ("prova_dup.pdf", pdf_prova_bytes, "application/pdf")},
        )
        assert resp_dup.status_code == 409
        assert resp_dup.json()["prova_id"] == str(prova_id)

        # 3. GET /api/v1/provas e GET /api/v1/provas/{id}
        resp_lista = client.get("/api/v1/provas")
        assert resp_lista.status_code == 200
        assert resp_lista.json()["total"] == 1

        resp_detalhe = client.get(f"/api/v1/provas/{prova_id}")
        assert resp_detalhe.status_code == 200
        detalhe = resp_detalhe.json()
        assert detalhe["ultima_ingestao"]["status"] == "concluida"
        assert detalhe["ultima_ingestao"]["metadados"]["imagens_detectadas"] == 5
        assert detalhe["ultima_ingestao"]["metadados"]["imagens_filtradas_margem"] == 3
        assert detalhe["ultima_ingestao"]["metadados"]["gabarito_enviado"] is True
        assert detalhe["questoes"]["total"] == 3
        assert detalhe["questoes"]["gabarito_validas"] == 2
        assert detalhe["questoes"]["gabarito_pendentes"] == 1
        assert detalhe["alertas"]["criticos_abertos"] == 1  # Q12 alternativas_incompletas
        assert detalhe["alertas"]["abertos"] >= 2  # Q12 critica + Q11/Q12 fonte_symbol_detectada (pagina 2)
        assert detalhe["classificacao_encadeada"] == {
            "solicitada": True,
            "taxonomia_id": str(tax.id),
            "perfil_id": None,
            "execucao_id": str(exec_encadeada_id),
            "status": "agendada",
        }
        assert len(hook_chamadas) == 1

        # 4. Entrega controlada de mídia e renderização de página PDF
        questoes_db = repo_questoes.listar_por_prova(prova_id)
        por_num = {q.numero: q for q in questoes_db}
        ativo_q10 = por_num[10].ativos_visuais[0]
        ativo_q11 = por_num[11].ativos_visuais[0]
        assert ativo_q10.chave_arquivo is not None
        assert ativo_q11.chave_arquivo is not None

        resp_ativo = client.get(f"/api/v1/ativos-visuais/{ativo_q10.id}/arquivo")
        assert resp_ativo.status_code == 200
        assert resp_ativo.headers["content-type"] == "image/png"
        assert resp_ativo.content.startswith(b"\x89PNG\r\n\x1a\n")
        etag_ativo = resp_ativo.headers["etag"]
        assert "Cache-Control" in resp_ativo.headers

        resp_ativo_304 = client.get(
            f"/api/v1/ativos-visuais/{ativo_q10.id}/arquivo",
            headers={"If-None-Match": etag_ativo},
        )
        assert resp_ativo_304.status_code == 304
        assert resp_ativo_304.content == b""

        resp_ativo_304_fraco = client.get(
            f"/api/v1/ativos-visuais/{ativo_q10.id}/arquivo",
            headers={"If-None-Match": f"W/{etag_ativo}"},
        )
        assert resp_ativo_304_fraco.status_code == 304

        resp_pagina = client.get(f"/api/v1/provas/{prova_id}/paginas/1/imagem")
        assert resp_pagina.status_code == 200
        assert resp_pagina.headers["content-type"] == "image/png"
        assert resp_pagina.content.startswith(b"\x89PNG\r\n\x1a\n")
        etag_pagina = resp_pagina.headers["etag"]
        assert "Cache-Control" in resp_pagina.headers

        resp_pagina_304 = client.get(
            f"/api/v1/provas/{prova_id}/paginas/1/imagem",
            headers={"If-None-Match": etag_pagina},
        )
        assert resp_pagina_304.status_code == 304
        assert resp_pagina_304.content == b""

        assert client.get(f"/api/v1/provas/{prova_id}/paginas/0/imagem").status_code == 422
        assert client.get(f"/api/v1/provas/{prova_id}/paginas/99/imagem").status_code == 404
        assert client.get(f"/api/v1/ativos-visuais/{uuid4()}/arquivo").status_code == 404

        # 5. PUT /api/v1/provas/{id}/gabarito preservando Classificações e edições manuais
        classif_q10 = repo_classif.salvar(
            Classificacao(
                questao_id=por_num[10].id,
                taxonomia_id=tax.id,
                disciplina_principal="algoritmos",
                topicos=("Complexidade",),
                justificativa="Classificação humana prévia.",
                confianca=1.0,
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
            )
        )
        q10_editada = por_num[10]
        q10_editada.editar_conteudo(enunciado="Enunciado revisado manualmente pelo professor na Q10.")
        repo_questoes.salvar(q10_editada)

        # 5a. Upload inválido de gabarito NÃO sobrescreve gabarito.pdf anterior
        resp_gab_invalido = client.put(
            f"/api/v1/provas/{prova_id}/gabarito",
            files={"arquivo_gabarito": ("gab_ruim.pdf", b"%PDF-1.4 INVALIDO", "application/pdf")},
        )
        assert resp_gab_invalido.status_code == 422
        armazenamento = ArmazenamentoArquivosLocal(data_dir)
        assert armazenamento.ler(f"provas/{prova_id}/gabarito.pdf") == pdf_gab_inicial

        # 5b. Upload válido de gabarito definitivo:
        # Q10: mantida (A -> A); Q11: alterada + anulada; Q12: sem gabarito; Q05: sem correspondência
        extrator_gab.itens_por_marcador[b"DEFINITIVO"] = (
            ItemGabaritoExtraido(5, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.D)),
            ItemGabaritoExtraido(10, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A)),
            ItemGabaritoExtraido(11, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.ANULADA)),
        )
        resp_gab = client.put(
            f"/api/v1/provas/{prova_id}/gabarito",
            files={"arquivo_gabarito": ("gab_def.pdf", b"%PDF-1.4 DEFINITIVO", "application/pdf")},
        )
        assert resp_gab.status_code == 200
        assert resp_gab.json() == {
            "mantidas": 1,
            "alteradas": 1,
            "anuladas": 1,
            "sem_correspondencia": [5],
            "questoes_sem_gabarito": [12],
        }

        classif_apos_gab = repo_classif.buscar_por_id(classif_q10.id)
        assert classif_apos_gab is not None and classif_apos_gab.vigente is True
        q10_apos_gab = repo_questoes.buscar_por_id(por_num[10].id)
        q11_apos_gab = repo_questoes.buscar_por_id(por_num[11].id)
        q12_apos_gab = repo_questoes.buscar_por_id(por_num[12].id)
        assert q10_apos_gab is not None and q10_apos_gab.editada_manualmente is True
        assert q10_apos_gab.enunciado == "Enunciado revisado manualmente pelo professor na Q10."
        assert q11_apos_gab is not None and q11_apos_gab.gabarito == Gabarito(SituacaoGabarito.ANULADA)
        assert q12_apos_gab is not None
        assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA in q12_apos_gab.codigos_alertas_abertos

        # 5c. Novo gabarito completo resolve gabarito_ausente_na_prova da Q12
        extrator_gab.itens_por_marcador[b"COMPLETO"] = (
            ItemGabaritoExtraido(10, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A)),
            ItemGabaritoExtraido(11, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.ANULADA)),
            ItemGabaritoExtraido(12, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)),
        )
        resp_gab_completo = client.put(
            f"/api/v1/provas/{prova_id}/gabarito",
            files={"arquivo_gabarito": ("gab_comp.pdf", b"%PDF-1.4 COMPLETO", "application/pdf")},
        )
        assert resp_gab_completo.status_code == 200
        assert resp_gab_completo.json() == {
            "mantidas": 2,
            "alteradas": 1,
            "anuladas": 1,
            "sem_correspondencia": [],
            "questoes_sem_gabarito": [],
        }
        q12_resolvida = repo_questoes.buscar_por_id(por_num[12].id)
        assert q12_resolvida is not None
        assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA not in q12_resolvida.codigos_alertas_abertos

        # 6. POST /api/v1/provas/{id}/reprocessar (sobrescrever_editadas=false preserva Q10 + ativo PNG)
        extrator_prova.versao = 2
        chave_ativo_q10_antes = ativo_q10.chave_arquivo
        chave_ativo_q11_antes = ativo_q11.chave_arquivo

        resp_rep_false = client.post(
            f"/api/v1/provas/{prova_id}/reprocessar",
            json={"sobrescrever_editadas": False},
        )
        assert resp_rep_false.status_code == 202
        assert resp_rep_false.json()["sobrescrever_editadas"] is False
        app.state.worker.aguardar_ocioso(timeout=10.0)

        q10_preservada = repo_questoes.buscar_por_id(por_num[10].id)
        q11_atualizada = repo_questoes.buscar_por_id(por_num[11].id)
        assert q10_preservada is not None
        assert q10_preservada.editada_manualmente is True
        assert q10_preservada.enunciado == "Enunciado revisado manualmente pelo professor na Q10."
        assert armazenamento.existe(chave_ativo_q10_antes)

        assert q11_atualizada is not None
        assert q11_atualizada.id == por_num[11].id
        assert "v2" in q11_atualizada.enunciado
        assert q11_atualizada.gabarito == Gabarito(SituacaoGabarito.ANULADA)
        assert not armazenamento.existe(chave_ativo_q11_antes)
        assert q11_atualizada.ativos_visuais[0].chave_arquivo is not None
        assert armazenamento.existe(q11_atualizada.ativos_visuais[0].chave_arquivo)
        assert repo_classif.buscar_por_id(classif_q10.id) is not None

        # 7. POST /api/v1/provas/{id}/reprocessar (sobrescrever_editadas=true sobrescreve Q10, mantém Classificação)
        extrator_prova.versao = 3
        resp_rep_true = client.post(
            f"/api/v1/provas/{prova_id}/reprocessar",
            json={"sobrescrever_editadas": True},
        )
        assert resp_rep_true.status_code == 202
        app.state.worker.aguardar_ocioso(timeout=10.0)

        q10_sobrescrita = repo_questoes.buscar_por_id(por_num[10].id)
        assert q10_sobrescrita is not None
        assert q10_sobrescrita.id == por_num[10].id
        assert q10_sobrescrita.editada_manualmente is False
        assert "v3" in q10_sobrescrita.enunciado
        assert repo_classif.buscar_por_id(classif_q10.id) is not None


def test_provas_validacoes_erros_e_retentativa_de_falha(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    extrator_prova = _FakeExtratorProvaRico()
    extrator_prova.deve_falhar = True
    extrator_gab = _FakeExtratorGabaritoStateful()
    data_dir = tmp_path / "app_data"

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=data_dir),
        extrator_prova=extrator_prova,
        extrator_gabarito=extrator_gab,
    )
    pdf_bytes = _gerar_pdf_bytes_valido(1)

    with TestClient(app) as client:
        # Ano sem faixa padrão sem override -> 422
        assert (
            client.post(
                "/api/v1/provas",
                data={"exame": "ENADE", "curso": "Engenharia de Computação", "ano": "2021"},
                files={"arquivo_prova": ("prova.pdf", pdf_bytes, "application/pdf")},
            ).status_code
            == 422
        )

        # Override parcial -> 422
        assert (
            client.post(
                "/api/v1/provas",
                data={"exame": "ENADE", "curso": "Engenharia de Computação", "ano": "2023", "questao_inicio": "10"},
                files={"arquivo_prova": ("prova.pdf", pdf_bytes, "application/pdf")},
            ).status_code
            == 422
        )

        # Arquivo não-PDF -> 422
        assert (
            client.post(
                "/api/v1/provas",
                data={"exame": "ENADE", "curso": "Engenharia de Computação", "ano": "2023"},
                files={"arquivo_prova": ("prova.txt", b"nao eh pdf", "text/plain")},
            ).status_code
            == 422
        )

        # Taxonomia inexistente -> 404
        assert (
            client.post(
                "/api/v1/provas",
                data={
                    "exame": "ENADE",
                    "curso": "Engenharia de Computação",
                    "ano": "2023",
                    "taxonomia_id": str(uuid4()),
                },
                files={"arquivo_prova": ("prova.pdf", pdf_bytes, "application/pdf")},
            ).status_code
            == 404
        )

        # Prova inexistente -> 404
        assert client.get(f"/api/v1/provas/{uuid4()}").status_code == 404

        # Enfileira prova com falha na extração -> status erro -> retenta via POST /reprocessar
        resp_post = client.post(
            "/api/v1/provas",
            data={"exame": "ENADE", "curso": "Engenharia de Computação", "ano": "2023"},
            files={"arquivo_prova": ("prova.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp_post.status_code == 202
        prova_id = UUID(resp_post.json()["prova_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)

        det_erro = client.get(f"/api/v1/provas/{prova_id}").json()
        assert det_erro["ultima_ingestao"]["status"] == "erro"
        assert "Erro simulado" in det_erro["ultima_ingestao"]["mensagem_erro"]

        extrator_prova.deve_falhar = False
        resp_retry = client.post(f"/api/v1/provas/{prova_id}/reprocessar")
        assert resp_retry.status_code == 202
        app.state.worker.aguardar_ocioso(timeout=10.0)

        det_ok = client.get(f"/api/v1/provas/{prova_id}").json()
        assert det_ok["ultima_ingestao"]["status"] == "concluida"
        assert det_ok["questoes"]["total"] == 3

        # Simula ingestão pendente/processando -> PUT /gabarito e POST /reprocessar retornam 409
        repo_ing = RepositorioIngestoesSqlAlchemy(session_factory_teste)
        ing_pendente = Ingestao(prova_id=prova_id, status=StatusIngestao.PENDENTE, criada_em=datetime.now(UTC))
        repo_ing.salvar(ing_pendente)

        assert (
            client.put(
                f"/api/v1/provas/{prova_id}/gabarito",
                files={"arquivo_gabarito": ("gab.pdf", b"%PDF-1.4 ok", "application/pdf")},
            ).status_code
            == 409
        )
        assert client.post(f"/api/v1/provas/{prova_id}/reprocessar").status_code == 409


@pytest.mark.enade_real
def test_smoke_api_provas_com_extratores_reais_enade_2023(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    if not PROVA_2023_REAL.is_file() or not GAB_2023_REAL.is_file():
        pytest.skip("PDFs oficiais do ENADE 2023 ausentes localmente.")

    # Fatia de 2 páginas (p. 14 com Q10 e p. 17 com Q13/fórmula) para smoke test rápido com Docling real
    src = pdfium.PdfDocument(str(PROVA_2023_REAL))
    dst = pdfium.PdfDocument.new()
    try:
        dst.import_pages(src, pages=[13, 16])
        buf = BytesIO()
        dst.save(buf)
        pdf_slice_bytes = buf.getvalue()
    finally:
        dst.close()
        src.close()

    gab_bytes = GAB_2023_REAL.read_bytes()
    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_real"),
        extrator_prova=ExtratorProvaDocling(),
        extrator_gabarito=ExtratorGabaritoPdfPlumber(),
        renderizador=RenderizadorPaginaPdfPypdfium2(),
    )

    with TestClient(app) as client:
        resp_post = client.post(
            "/api/v1/provas",
            data={
                "exame": "ENADE",
                "curso": "Engenharia de Computação",
                "ano": "2023",
                "questao_inicio": "10",
                "questao_fim": "13",
            },
            files={
                "arquivo_prova": ("enade_2023_slice.pdf", pdf_slice_bytes, "application/pdf"),
                "arquivo_gabarito": ("gab_2023.pdf", gab_bytes, "application/pdf"),
            },
        )
        assert resp_post.status_code == 202
        prova_id = UUID(resp_post.json()["prova_id"])

        app.state.worker.aguardar_ocioso(timeout=180.0)

        resp_detalhe = client.get(f"/api/v1/provas/{prova_id}")
        assert resp_detalhe.status_code == 200
        detalhe = resp_detalhe.json()
        assert detalhe["ultima_ingestao"]["status"] == "concluida"
        assert detalhe["questoes"]["total"] >= 2
        assert detalhe["questoes"]["gabarito_validas"] >= 2

        resp_pag = client.get(f"/api/v1/provas/{prova_id}/paginas/1/imagem")
        assert resp_pag.status_code == 200
        assert resp_pag.headers["content-type"] == "image/png"
        assert resp_pag.content.startswith(b"\x89PNG\r\n\x1a\n")
        etag = resp_pag.headers["etag"]
        assert (
            client.get(
                f"/api/v1/provas/{prova_id}/paginas/1/imagem",
                headers={"If-None-Match": etag},
            ).status_code
            == 304
        )

        questoes_db = RepositorioQuestoesSqlAlchemy(session_factory_teste).listar_por_prova(prova_id)
        ativos = [ativo for q in questoes_db for ativo in q.ativos_visuais]
        assert len(ativos) >= 1
        resp_ativo = client.get(f"/api/v1/ativos-visuais/{ativos[0].id}/arquivo")
        assert resp_ativo.status_code == 200
        assert resp_ativo.headers["content-type"] == "image/png"
        assert resp_ativo.content.startswith(b"\x89PNG\r\n\x1a\n")
