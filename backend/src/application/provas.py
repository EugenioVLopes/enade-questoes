"""Casos de uso de Provas, Ingestão, atualização de Gabarito e Reprocessamento."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from application.exceptions import (
    ArquivoPdfAusenteError,
    ConflitoEstadoIngestaoError,
    ConflitoProvaExistenteError,
    RecursoNaoEncontradoError,
)
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.extracao import ExtratorGabarito
from application.ports.repositorios import (
    RepositorioExecucoesClassificacao,
    RepositorioIngestoes,
    RepositorioPerfisClassificacao,
    RepositorioProvas,
    RepositorioQuestoes,
    RepositorioTaxonomias,
)
from application.worker import WorkerLocal
from domain.enums import SituacaoGabarito, StatusIngestao
from domain.exceptions import ErroValidacaoDominio
from domain.faixas_enade import resolver_faixa_componente_especifico
from domain.prova import Ingestao, MetadadosIngestao, Prova
from domain.reprocessamento import ResumoAtualizacaoGabarito, aplicar_gabarito_na_prova


def _agora_utc() -> datetime:
    return datetime.now(UTC)


def _validar_pdf_bytes(conteudo: bytes, campo: str) -> None:
    if not conteudo:
        raise ErroValidacaoDominio(f"O arquivo '{campo}' não pode estar vazio.")
    if b"%PDF-" not in conteudo[:1024]:
        raise ErroValidacaoDominio(f"O arquivo '{campo}' deve ser um PDF válido (cabeçalho %PDF- ausente).")


@dataclass(frozen=True, slots=True)
class ResultadoCriacaoProva:
    prova: Prova
    ingestao: Ingestao


@dataclass(frozen=True, slots=True)
class ResultadoReprocessamentoAceito:
    prova: Prova
    ingestao: Ingestao
    sobrescrever_editadas: bool


@dataclass(frozen=True, slots=True)
class ContagemQuestoesProva:
    total: int
    editadas_manualmente: int
    gabarito_validas: int
    gabarito_anuladas: int
    gabarito_pendentes: int


@dataclass(frozen=True, slots=True)
class ContagemAlertasProva:
    abertos: int
    criticos_abertos: int
    questoes_com_alerta_aberto: int


@dataclass(frozen=True, slots=True)
class StatusClassificacaoEncadeada:
    solicitada: bool
    taxonomia_id: UUID | None = None
    perfil_id: UUID | None = None
    execucao_id: UUID | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class DetalheProva:
    prova: Prova
    ultima_ingestao: Ingestao | None
    questoes: ContagemQuestoesProva
    alertas: ContagemAlertasProva
    classificacao_encadeada: StatusClassificacaoEncadeada


def _montar_detalhe_prova(
    prova: Prova,
    *,
    repo_ingestoes: RepositorioIngestoes,
    repo_questoes: RepositorioQuestoes,
    repo_execucoes: RepositorioExecucoesClassificacao,
) -> DetalheProva:
    ultima_ingestao = repo_ingestoes.buscar_ultima_por_prova(prova.id)
    questoes = repo_questoes.listar_por_prova(prova.id)

    contagem_questoes = ContagemQuestoesProva(
        total=len(questoes),
        editadas_manualmente=sum(1 for q in questoes if q.editada_manualmente),
        gabarito_validas=sum(1 for q in questoes if q.gabarito.situacao_gabarito == SituacaoGabarito.VALIDA),
        gabarito_anuladas=sum(1 for q in questoes if q.gabarito.situacao_gabarito == SituacaoGabarito.ANULADA),
        gabarito_pendentes=sum(1 for q in questoes if q.gabarito.situacao_gabarito == SituacaoGabarito.PENDENTE),
    )

    contagem_alertas = ContagemAlertasProva(
        abertos=sum(1 for q in questoes for a in q.alertas_extracao if a.is_aberto),
        criticos_abertos=sum(1 for q in questoes for a in q.alertas_extracao if a.is_aberto and a.is_critico),
        questoes_com_alerta_aberto=sum(1 for q in questoes if any(a.is_aberto for a in q.alertas_extracao)),
    )

    if ultima_ingestao is not None and ultima_ingestao.metadados.taxonomia_id_encadeada is not None:
        execucao_id = ultima_ingestao.metadados.execucao_classificacao_id
        status_enc = ultima_ingestao.metadados.status_classificacao_encadeada
        if execucao_id is not None:
            execucao = repo_execucoes.buscar_por_id(execucao_id)
            if execucao is not None:
                status_enc = execucao.status.value
        elif status_enc is None:
            if ultima_ingestao.status in {StatusIngestao.PENDENTE, StatusIngestao.PROCESSANDO}:
                status_enc = "aguardando_ingestao"
            else:
                status_enc = "nao_executada"

        classificacao_encadeada = StatusClassificacaoEncadeada(
            solicitada=True,
            taxonomia_id=ultima_ingestao.metadados.taxonomia_id_encadeada,
            perfil_id=ultima_ingestao.metadados.perfil_id_encadeada,
            execucao_id=execucao_id,
            status=status_enc,
        )
    else:
        classificacao_encadeada = StatusClassificacaoEncadeada(solicitada=False)

    return DetalheProva(
        prova=prova,
        ultima_ingestao=ultima_ingestao,
        questoes=contagem_questoes,
        alertas=contagem_alertas,
        classificacao_encadeada=classificacao_encadeada,
    )


class CriarProvaUseCase:
    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        repo_ingestoes: RepositorioIngestoes,
        repo_taxonomias: RepositorioTaxonomias,
        repo_perfis: RepositorioPerfisClassificacao,
        armazenamento: ArmazenamentoArquivos,
        worker: WorkerLocal,
    ) -> None:
        self._repo_provas = repo_provas
        self._repo_ingestoes = repo_ingestoes
        self._repo_taxonomias = repo_taxonomias
        self._repo_perfis = repo_perfis
        self._armazenamento = armazenamento
        self._worker = worker

    def execute(
        self,
        *,
        exame: str,
        curso: str,
        ano: int,
        conteudo_prova_pdf: bytes,
        conteudo_gabarito_pdf: bytes | None = None,
        questao_inicio: int | None = None,
        questao_fim: int | None = None,
        taxonomia_id: UUID | None = None,
        perfil_id: UUID | None = None,
    ) -> ResultadoCriacaoProva:
        _validar_pdf_bytes(conteudo_prova_pdf, "arquivo_prova")
        if conteudo_gabarito_pdf is not None:
            _validar_pdf_bytes(conteudo_gabarito_pdf, "arquivo_gabarito")

        faixa_ce = resolver_faixa_componente_especifico(ano, questao_inicio, questao_fim)
        prova = Prova(exame=exame, curso=curso, ano=ano, faixa_ce=faixa_ce)

        if perfil_id is not None and taxonomia_id is None:
            raise ErroValidacaoDominio("'perfil_id' só pode ser informado quando 'taxonomia_id' também for enviado.")
        if taxonomia_id is not None:
            taxonomia = self._repo_taxonomias.buscar_por_id(taxonomia_id)
            if taxonomia is None:
                raise RecursoNaoEncontradoError(f"Taxonomia '{taxonomia_id}' não encontrada.")
            if not taxonomia.ativas():
                raise ErroValidacaoDominio(
                    f"Taxonomia '{taxonomia.codigo}' não possui disciplinas ativas para classificação encadeada."
                )
        if perfil_id is not None and self._repo_perfis.buscar_por_id(perfil_id) is None:
            raise RecursoNaoEncontradoError(f"Perfil de classificação '{perfil_id}' não encontrado.")

        existente = self._repo_provas.buscar_por_chave_natural(prova.exame, prova.curso, prova.ano)
        if existente is not None:
            raise ConflitoProvaExistenteError(existente.id, existente.exame, existente.curso, existente.ano)

        chave_prova = f"provas/{prova.id}/prova.pdf"
        chave_gabarito = f"provas/{prova.id}/gabarito.pdf" if conteudo_gabarito_pdf is not None else None

        self._armazenamento.salvar(chave_prova, conteudo_prova_pdf)
        if chave_gabarito is not None and conteudo_gabarito_pdf is not None:
            self._armazenamento.salvar(chave_gabarito, conteudo_gabarito_pdf)

        prova.caminho_pdf = chave_prova
        prova.caminho_gabarito = chave_gabarito

        try:
            prova_salva = self._repo_provas.salvar(prova)
        except Exception:
            self._limpar_chaves([chave_prova, chave_gabarito])
            existente_corrida = self._repo_provas.buscar_por_chave_natural(prova.exame, prova.curso, prova.ano)
            if existente_corrida is not None:
                raise ConflitoProvaExistenteError(
                    existente_corrida.id,
                    existente_corrida.exame,
                    existente_corrida.curso,
                    existente_corrida.ano,
                ) from None
            raise

        ingestao = Ingestao(
            prova_id=prova_salva.id,
            status=StatusIngestao.PENDENTE,
            metadados=MetadadosIngestao(
                gabarito_enviado=chave_gabarito is not None,
                taxonomia_id_encadeada=taxonomia_id,
                perfil_id_encadeada=perfil_id,
                status_classificacao_encadeada="aguardando_ingestao" if taxonomia_id is not None else None,
            ),
        )
        ingestao_salva = self._repo_ingestoes.salvar(ingestao)
        self._worker.enfileirar_ingestao(prova_salva.id, ingestao_salva.id)
        return ResultadoCriacaoProva(prova=prova_salva, ingestao=ingestao_salva)

    def _limpar_chaves(self, chaves: list[str | None]) -> None:
        for chave in chaves:
            if chave is not None:
                try:
                    self._armazenamento.remover(chave)
                except Exception:  # noqa: S110
                    pass


class ListarProvasUseCase:
    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        repo_ingestoes: RepositorioIngestoes,
        repo_questoes: RepositorioQuestoes,
        repo_execucoes: RepositorioExecucoesClassificacao,
    ) -> None:
        self._repo_provas = repo_provas
        self._repo_ingestoes = repo_ingestoes
        self._repo_questoes = repo_questoes
        self._repo_execucoes = repo_execucoes

    def execute(self) -> list[DetalheProva]:
        provas = self._repo_provas.listar()
        return [
            _montar_detalhe_prova(
                prova,
                repo_ingestoes=self._repo_ingestoes,
                repo_questoes=self._repo_questoes,
                repo_execucoes=self._repo_execucoes,
            )
            for prova in provas
        ]


class ObterProvaUseCase:
    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        repo_ingestoes: RepositorioIngestoes,
        repo_questoes: RepositorioQuestoes,
        repo_execucoes: RepositorioExecucoesClassificacao,
    ) -> None:
        self._repo_provas = repo_provas
        self._repo_ingestoes = repo_ingestoes
        self._repo_questoes = repo_questoes
        self._repo_execucoes = repo_execucoes

    def execute(self, prova_id: UUID) -> DetalheProva:
        prova = self._repo_provas.buscar_por_id(prova_id)
        if prova is None:
            raise RecursoNaoEncontradoError(f"Prova '{prova_id}' não encontrada.")
        return _montar_detalhe_prova(
            prova,
            repo_ingestoes=self._repo_ingestoes,
            repo_questoes=self._repo_questoes,
            repo_execucoes=self._repo_execucoes,
        )


class AtualizarGabaritoUseCase:
    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        repo_ingestoes: RepositorioIngestoes,
        repo_questoes: RepositorioQuestoes,
        armazenamento: ArmazenamentoArquivos,
        extrator_gabarito: ExtratorGabarito,
    ) -> None:
        self._repo_provas = repo_provas
        self._repo_ingestoes = repo_ingestoes
        self._repo_questoes = repo_questoes
        self._armazenamento = armazenamento
        self._extrator_gabarito = extrator_gabarito

    def execute(self, prova_id: UUID, conteudo_gabarito_pdf: bytes) -> ResumoAtualizacaoGabarito:
        prova = self._repo_provas.buscar_por_id(prova_id)
        if prova is None:
            raise RecursoNaoEncontradoError(f"Prova '{prova_id}' não encontrada.")

        ultima_ingestao = self._repo_ingestoes.buscar_ultima_por_prova(prova.id)
        if ultima_ingestao is not None and ultima_ingestao.status in {
            StatusIngestao.PENDENTE,
            StatusIngestao.PROCESSANDO,
        }:
            raise ConflitoEstadoIngestaoError(
                "Não é possível atualizar o gabarito enquanto há ingestão pendente ou em processamento."
            )

        _validar_pdf_bytes(conteudo_gabarito_pdf, "arquivo_gabarito")

        # Valida e extrai em arquivo temporário antes de sobrescrever o gabarito existente em disco.
        with tempfile.TemporaryDirectory(prefix="enade-gabarito-") as tmp_dir:
            caminho_tmp = Path(tmp_dir) / "gabarito.pdf"
            caminho_tmp.write_bytes(conteudo_gabarito_pdf)
            resultado_gab = self._extrator_gabarito.extrair(caminho_tmp)

        chave_gabarito = f"provas/{prova.id}/gabarito.pdf"
        agora = _agora_utc()
        gabaritos_por_numero = resultado_gab.mapa_objetivas()

        # O PDF é gravado de forma compensável: se a gravação das Questões falhar, o arquivo anterior é restaurado
        # e nem `caminho_gabarito` nem `gabarito_enviado` chegam a mudar.
        conteudo_anterior = (
            self._armazenamento.ler(chave_gabarito) if self._armazenamento.existe(chave_gabarito) else None
        )
        self._armazenamento.salvar(chave_gabarito, conteudo_gabarito_pdf)
        try:
            # Leitura, aplicação e gravação numa só transação, com as linhas travadas: edição concorrente do revisor
            # é preservada (o gabarito é aplicado sobre ela) e nunca gera conflito de versão.
            resumo = self._repo_questoes.atualizar_por_prova(
                prova.id, lambda questoes: aplicar_gabarito_na_prova(questoes, gabaritos_por_numero, agora)
            )
        except Exception:
            if conteudo_anterior is not None:
                self._armazenamento.salvar(chave_gabarito, conteudo_anterior)
            else:
                self._armazenamento.remover(chave_gabarito)
            raise

        prova.caminho_gabarito = chave_gabarito
        prova.atualizada_em = agora
        self._repo_provas.salvar(prova)

        if ultima_ingestao is not None and not ultima_ingestao.metadados.gabarito_enviado:
            ultima_ingestao.metadados = replace(ultima_ingestao.metadados, gabarito_enviado=True)
            self._repo_ingestoes.salvar(ultima_ingestao)

        return resumo


class ReprocessarProvaUseCase:
    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        repo_ingestoes: RepositorioIngestoes,
        armazenamento: ArmazenamentoArquivos,
        worker: WorkerLocal,
    ) -> None:
        self._repo_provas = repo_provas
        self._repo_ingestoes = repo_ingestoes
        self._armazenamento = armazenamento
        self._worker = worker

    def execute(self, prova_id: UUID, *, sobrescrever_editadas: bool = False) -> ResultadoReprocessamentoAceito:
        prova = self._repo_provas.buscar_por_id(prova_id)
        if prova is None:
            raise RecursoNaoEncontradoError(f"Prova '{prova_id}' não encontrada.")

        if not prova.caminho_pdf or not self._armazenamento.existe(prova.caminho_pdf):
            raise ArquivoPdfAusenteError(f"Arquivo PDF da prova '{prova_id}' não encontrado no armazenamento.")

        ultima_ingestao = self._repo_ingestoes.buscar_ultima_por_prova(prova.id)
        if ultima_ingestao is not None and ultima_ingestao.status in {
            StatusIngestao.PENDENTE,
            StatusIngestao.PROCESSANDO,
        }:
            raise ConflitoEstadoIngestaoError("Já existe uma ingestão pendente ou em processamento para esta prova.")

        preservar_encadeamento = bool(
            ultima_ingestao is not None
            and ultima_ingestao.status in {StatusIngestao.ERRO, StatusIngestao.INTERROMPIDA}
            and ultima_ingestao.metadados.taxonomia_id_encadeada is not None
            and ultima_ingestao.metadados.execucao_classificacao_id is None
        )
        taxonomia_id = ultima_ingestao.metadados.taxonomia_id_encadeada if preservar_encadeamento else None
        perfil_id = ultima_ingestao.metadados.perfil_id_encadeada if preservar_encadeamento else None

        nova_ingestao = Ingestao(
            prova_id=prova.id,
            status=StatusIngestao.PENDENTE,
            metadados=MetadadosIngestao(
                gabarito_enviado=prova.caminho_gabarito is not None,
                taxonomia_id_encadeada=taxonomia_id,
                perfil_id_encadeada=perfil_id,
                status_classificacao_encadeada="aguardando_ingestao" if taxonomia_id is not None else None,
            ),
        )
        ingestao_salva = self._repo_ingestoes.salvar(nova_ingestao)
        self._worker.enfileirar_ingestao(
            prova.id,
            ingestao_salva.id,
            sobrescrever_editadas=sobrescrever_editadas,
        )
        return ResultadoReprocessamentoAceito(
            prova=prova,
            ingestao=ingestao_salva,
            sobrescrever_editadas=sobrescrever_editadas,
        )
