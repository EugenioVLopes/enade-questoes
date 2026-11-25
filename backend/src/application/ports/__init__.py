"""Contratos (Protocol) e DTOs das portas da camada de aplicação."""

from __future__ import annotations

from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.avaliacao import ConsultaAvaliacao, RegistroHistoricoClassificacao
from application.ports.classificacao import (
    ClassificadorMultimodal,
    IdentidadeClassificador,
    ResultadoChamada,
)
from application.ports.extracao import (
    AlternativaExtraida,
    AtivoVisualExtraido,
    ExtratorGabarito,
    ExtratorProva,
    ItemGabaritoExtraido,
    QuestaoExtraida,
    RenderizadorPaginaPdf,
    ResultadoExtracaoGabarito,
    ResultadoExtracaoProva,
)
from application.ports.repositorios import (
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
)

__all__ = [
    "AlternativaExtraida",
    "ArmazenamentoArquivos",
    "AtivoVisualExtraido",
    "ClassificadorMultimodal",
    "ConsultaAvaliacao",
    "ExtratorGabarito",
    "ExtratorProva",
    "IdentidadeClassificador",
    "ItemGabaritoExtraido",
    "QuestaoExtraida",
    "RegistroHistoricoClassificacao",
    "RenderizadorPaginaPdf",
    "RepositorioAtivosVisuais",
    "RepositorioClassificacoes",
    "RepositorioConjuntoOuro",
    "RepositorioDivergenciasReclassificacao",
    "RepositorioExecucoesClassificacao",
    "RepositorioIngestoes",
    "RepositorioPerfisClassificacao",
    "RepositorioProvas",
    "RepositorioQuestoes",
    "RepositorioTaxonomias",
    "ResultadoChamada",
    "ResultadoExtracaoGabarito",
    "ResultadoExtracaoProva",
]
