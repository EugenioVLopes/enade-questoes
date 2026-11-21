from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from application.ports import (
    ArmazenamentoArquivos,
    ClassificadorMultimodal,
    ExtratorGabarito,
    ExtratorProva,
    IdentidadeClassificador,
    ItemGabaritoExtraido,
    RenderizadorPaginaPdf,
    RepositorioAtivosVisuais,
    RepositorioClassificacoes,
    RepositorioConjuntoOuro,
    RepositorioDivergenciasReclassificacao,
    RepositorioExecucoesClassificacao,
    RepositorioIngestoes,
    RepositorioPerfisClassificacao,
    RepositorioProvas,
    RepositorioQuestoes,
    RepositorioTaxonomias,
    ResultadoChamada,
    ResultadoExtracaoGabarito,
    ResultadoExtracaoProva,
)
from domain.avaliacao import ConjuntoOuro
from domain.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    ExecucaoClassificacao,
    PerfilClassificacao,
)
from domain.enums import (
    LetraAlternativa,
    OrigemClassificacao,
    ResolucaoDivergencia,
    SituacaoGabarito,
    StatusClassificacao,
    StatusDivergencia,
    TipoQuestao,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AtivoVisual, FaixaQuestoes, Gabarito, Ingestao, MetadadosIngestao, Prova, Questao
from domain.taxonomia import Taxonomia


class _FakeExtratorProva:
    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva:
        return ResultadoExtracaoProva(questoes=(), extracao_bruta_json="{}", metadados=MetadadosIngestao())


class _FakeExtratorGabarito:
    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito:
        return ResultadoExtracaoGabarito(
            itens=(
                ItemGabaritoExtraido(1, TipoQuestao.DISCURSIVA, Gabarito(SituacaoGabarito.PENDENTE), "DISCURSIVA 1"),
                ItemGabaritoExtraido(
                    10,
                    TipoQuestao.OBJETIVA,
                    Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C),
                    "10",
                ),
            )
        )


class _FakeRenderizadorPdf:
    def contar_paginas(self, caminho_pdf: Path) -> int:
        return 1

    def renderizar_pagina(self, caminho_pdf: Path, pagina: int, dpi: int = 150) -> bytes:
        return b"PNG"


class _FakeClassificador:
    @property
    def identidade(self) -> IdentidadeClassificador:
        return IdentidadeClassificador(provider="fake", model="fake-v1", base_url="http://fake")

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: Sequence[bytes],
        schema: Mapping[str, Any],
        nome_schema: str,
        max_tokens: int = 4096,
        usar_cache: bool = True,
    ) -> ResultadoChamada:
        return ResultadoChamada(
            dados_brutos={"disciplina_principal": "algoritmos"},
            prompt_tokens=10,
            completion_tokens=5,
            latencia_ms=1.0,
            from_cache=False,
            cache_key="abc",
        )


class _FakeArmazenamento:
    def __init__(self) -> None:
        self._dados: dict[str, bytes] = {}

    def salvar(self, chave: str, conteudo: bytes) -> str:
        self._dados[chave] = conteudo
        return chave

    def ler(self, chave: str) -> bytes:
        return self._dados[chave]

    def remover(self, chave: str) -> None:
        self._dados.pop(chave, None)

    def existe(self, chave: str) -> bool:
        return chave in self._dados

    def resolver_caminho(self, chave: str) -> Path:
        return Path(chave)


class _FakeRepositorios:
    def __init__(self) -> None:
        self.classificacoes: dict[UUID, Classificacao] = {}
        self.divergencias: dict[UUID, DivergenciaReclassificacao] = {}

    def salvar(self, obj: Any) -> Any:
        if isinstance(obj, Classificacao):
            self.classificacoes[obj.id] = obj
        elif isinstance(obj, DivergenciaReclassificacao):
            self.divergencias[obj.id] = obj
        return obj

    def salvar_lote(self, questoes: Sequence[Questao]) -> list[Questao]:
        return list(questoes)

    def buscar_por_id(self, obj_id: UUID) -> Any:
        return None

    def buscar_por_chave_natural(self, exame: str, curso: str, ano: int) -> Prova | None:
        return None

    def buscar_ultima_por_prova(self, prova_id: UUID) -> Ingestao | None:
        return None

    def listar_por_prova(self, prova_id: UUID) -> list[Any]:
        return []

    def buscar_por_prova_e_numero(self, prova_id: UUID, numero: int) -> Questao | None:
        return None

    def listar_por_questao(self, questao_id: UUID) -> list[AtivoVisual]:
        return []

    def remover(self, ativo_id: UUID) -> None:
        return None

    def buscar_por_codigo(self, codigo: str) -> Taxonomia | None:
        return None

    def buscar_por_codigo_e_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None:
        return None

    def contar_classificacoes_vigentes_por_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina_codigo: str,
    ) -> int:
        return 0

    def listar(self, **kwargs: Any) -> list[Any]:
        return []

    def marcar_em_processamento_como_interrompidas(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def registrar_substituicao(self, anterior: Classificacao, nova: Classificacao) -> Classificacao:
        return nova

    def buscar_vigente(self, questao_id: UUID, taxonomia_id: UUID) -> Classificacao | None:
        return None

    def listar_historico(self, questao_id: UUID, taxonomia_id: UUID) -> list[Classificacao]:
        return []

    def listar_vigentes_por_questao(self, questao_id: UUID) -> list[Classificacao]:
        return []

    def listar_fila_revisao(
        self,
        taxonomia_id: UUID,
        *,
        status: StatusClassificacao | None = None,
        apenas_revisao_prioritaria: bool = False,
    ) -> list[Classificacao]:
        return []

    def resolver_atomicamente(
        self,
        divergencia_id: UUID,
        resolucao: ResolucaoDivergencia,
        agora: datetime,
        nova_classificacao: Classificacao | None = None,
    ) -> DivergenciaReclassificacao:
        divergencia = self.divergencias[divergencia_id]
        vigente = self.classificacoes[divergencia.classificacao_vigente_id]

        if resolucao == ResolucaoDivergencia.EDITAR_MANUALMENTE:
            if nova_classificacao is None:
                raise ErroValidacaoDominio("Resolução 'editar_manualmente' exige nova_classificacao.")
            vigente.vigente = False
            self.classificacoes[nova_classificacao.id] = nova_classificacao
        elif resolucao == ResolucaoDivergencia.MANTER_HUMANA:
            if nova_classificacao is not None:
                raise ErroValidacaoDominio("Resolução 'manter_humana' exige nova_classificacao=None.")
        elif resolucao == ResolucaoDivergencia.ACEITAR_CANDIDATA:
            candidata = nova_classificacao or Classificacao(
                questao_id=divergencia.questao_id,
                taxonomia_id=divergencia.taxonomia_id,
                disciplina_principal=divergencia.disciplina_principal_candidata,
                disciplinas_secundarias=divergencia.disciplinas_secundarias_candidatas,
                topicos=divergencia.topicos_candidatos,
                justificativa=divergencia.justificativa_candidata,
                confianca=divergencia.confianca_candidata,
                origem=OrigemClassificacao.AUTOMATICA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
                execucao_id=divergencia.execucao_id,
                substitui_classificacao_id=vigente.id,
                criada_em=agora,
                revisada_em=agora,
            )
            vigente.vigente = False
            self.classificacoes[candidata.id] = candidata

        divergencia.resolver(resolucao, agora)
        return divergencia

    def exportar_elegiveis(self, taxonomia_codigo: str, agora: datetime) -> ConjuntoOuro:
        return ConjuntoOuro("1.0", taxonomia_codigo, agora, ())

    def salvar_snapshot(self, conjunto: ConjuntoOuro, destino: str) -> str:
        return destino

    def carregar_snapshot(self, origem: str) -> ConjuntoOuro:
        return ConjuntoOuro("1.0", "enade-ec", datetime.now(UTC), ())


def test_portas_nao_llm_e_llm_satisfazem_protocol_em_runtime() -> None:
    extrator_gab = _FakeExtratorGabarito()
    resultado_gab = extrator_gab.extrair(Path("gabarito.pdf"))
    assert resultado_gab.mapa_objetivas() == {10: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)}

    assert isinstance(_FakeExtratorProva(), ExtratorProva)
    assert isinstance(extrator_gab, ExtratorGabarito)
    assert isinstance(_FakeRenderizadorPdf(), RenderizadorPaginaPdf)
    assert isinstance(_FakeClassificador(), ClassificadorMultimodal)
    assert isinstance(_FakeArmazenamento(), ArmazenamentoArquivos)


def test_repositorios_satisfazem_protocolos_em_runtime() -> None:
    repo = _FakeRepositorios()
    for protocolo in (
        RepositorioProvas,
        RepositorioIngestoes,
        RepositorioQuestoes,
        RepositorioAtivosVisuais,
        RepositorioTaxonomias,
        RepositorioPerfisClassificacao,
        RepositorioExecucoesClassificacao,
        RepositorioClassificacoes,
        RepositorioDivergenciasReclassificacao,
        RepositorioConjuntoOuro,
    ):
        assert isinstance(repo, protocolo)

    # Verifica uso com entidades reais sem I/O
    assert isinstance(ExecucaoClassificacao, type)
    assert isinstance(StatusDivergencia.ABERTA.value, str)


def test_resolver_atomicamente_suporta_editar_manualmente_com_nova_classificacao() -> None:
    agora = datetime(2026, 11, 20, 21, 30, tzinfo=UTC)
    repo = _FakeRepositorios()
    questao_id = uuid4()
    taxonomia_id = uuid4()

    vigente = Classificacao(
        questao_id=questao_id,
        taxonomia_id=taxonomia_id,
        disciplina_principal="algoritmos",
        topicos=("grafos",),
        justificativa="Original humana.",
        confianca=1.0,
        origem=OrigemClassificacao.HUMANA,
        status=StatusClassificacao.APROVADA,
        vigente=True,
    )
    repo.salvar(vigente)

    divergencia = DivergenciaReclassificacao(
        questao_id=questao_id,
        taxonomia_id=taxonomia_id,
        execucao_id=uuid4(),
        classificacao_vigente_id=vigente.id,
        disciplina_principal_candidata="redes",
        confianca_candidata=0.91,
    )
    repo.salvar(divergencia)

    with pytest.raises(ErroValidacaoDominio):
        repo.resolver_atomicamente(divergencia.id, ResolucaoDivergencia.EDITAR_MANUALMENTE, agora)
    with pytest.raises(ErroValidacaoDominio):
        repo.resolver_atomicamente(
            divergencia.id,
            ResolucaoDivergencia.MANTER_HUMANA,
            agora,
            nova_classificacao=vigente,
        )

    nova_humana = vigente.substituir_por_correcao(
        disciplina_principal="sistemas-operacionais",
        disciplinas_secundarias=("algoritmos",),
        topicos=("Escalonamento",),
        justificativa="Decisão manual na resolução da divergência.",
        agora=agora,
    )
    resolvida = repo.resolver_atomicamente(
        divergencia.id,
        ResolucaoDivergencia.EDITAR_MANUALMENTE,
        agora,
        nova_classificacao=nova_humana,
    )

    assert resolvida.status == StatusDivergencia.RESOLVIDA
    assert resolvida.resolucao == ResolucaoDivergencia.EDITAR_MANUALMENTE
    assert resolvida.resolvida_em == agora
    assert repo.classificacoes[vigente.id].vigente is False
    assert repo.classificacoes[nova_humana.id].vigente is True
    assert repo.classificacoes[nova_humana.id].substitui_classificacao_id == vigente.id
