"""Execução de classificação."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from domain.classificacao.perfil import PerfilClassificacao
from domain.enums import EscopoExecucao, StatusExecucaoClassificacao
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.taxonomia import Taxonomia


def _congelar_valor(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return MappingProxyType({k: _congelar_valor(v) for k, v in valor.items()})
    if isinstance(valor, list | tuple):
        return tuple(_congelar_valor(v) for v in valor)
    if isinstance(valor, set | frozenset):
        return frozenset(_congelar_valor(v) for v in valor)
    return valor


def _validar_colecao_uuids(valor: Iterable[UUID | str], campo: str) -> tuple[UUID, ...]:
    if isinstance(valor, str | bytes | bytearray | memoryview | Mapping) or not isinstance(valor, Iterable):
        raise ErroValidacaoDominio(f"'{campo}' deve ser uma coleção iterável de UUIDs (não str/bytes/Mapping).")
    itens: list[UUID] = []
    for item in valor:
        if isinstance(item, UUID):
            itens.append(item)
        elif isinstance(item, str):
            try:
                itens.append(UUID(item.strip()))
            except (ValueError, TypeError, AttributeError) as err:
                raise ErroValidacaoDominio(f"Item inválido em '{campo}': {item!r}.") from err
        else:
            raise ErroValidacaoDominio(f"Item de '{campo}' deve ser UUID; recebido: {item!r}.")
    return tuple(dict.fromkeys(itens))


def _validar_nao_negativo_int(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroValidacaoDominio(f"'{campo}' deve ser inteiro >= 0; recebido: {valor!r}.")
    return valor


@dataclass(slots=True)
class ExecucaoClassificacao:
    """Rodada registrada de classificação automática preservando snapshots congelados."""

    taxonomia_id: UUID
    perfil_id: UUID
    snapshot_taxonomia: Mapping[str, Any]
    snapshot_perfil: Mapping[str, Any]
    escopo: EscopoExecucao = EscopoExecucao.TODAS
    incluir_revisadas: bool = False
    status: StatusExecucaoClassificacao = StatusExecucaoClassificacao.PENDENTE
    total_itens: int = 0
    processadas: int = 0
    divergencias_abertas: int = 0
    erros_por_questao: dict[str, str] = field(default_factory=dict)
    cache_hits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    criada_em: datetime | None = None
    iniciada_em: datetime | None = None
    concluida_em: datetime | None = None
    escopo_prova_id: UUID | None = None
    escopo_questao_ids: tuple[UUID, ...] = ()
    questao_ids_alvo: tuple[UUID, ...] = ()
    questao_ids_concluidas: tuple[UUID, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        try:
            self.escopo = EscopoExecucao(self.escopo)
            self.status = StatusExecucaoClassificacao(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Escopo ou status de execução inválido: {err}") from err

        if not isinstance(self.incluir_revisadas, bool):
            raise ErroValidacaoDominio("'incluir_revisadas' deve ser booleano.")

        if not isinstance(self.snapshot_taxonomia, Mapping) or not self.snapshot_taxonomia:
            raise ErroValidacaoDominio("ExecucaoClassificacao exige 'snapshot_taxonomia' não vazio.")
        if not isinstance(self.snapshot_perfil, Mapping) or not self.snapshot_perfil:
            raise ErroValidacaoDominio("ExecucaoClassificacao exige 'snapshot_perfil' não vazio.")

        self.snapshot_taxonomia = _congelar_valor(self.snapshot_taxonomia)
        self.snapshot_perfil = _congelar_valor(self.snapshot_perfil)

        if self.escopo_prova_id is not None and not isinstance(self.escopo_prova_id, UUID):
            try:
                self.escopo_prova_id = UUID(str(self.escopo_prova_id))
            except (ValueError, TypeError, AttributeError) as err:
                raise ErroValidacaoDominio(f"'escopo_prova_id' inválido: {self.escopo_prova_id!r}.") from err

        self.escopo_questao_ids = _validar_colecao_uuids(self.escopo_questao_ids, "escopo_questao_ids")
        self.questao_ids_alvo = _validar_colecao_uuids(self.questao_ids_alvo, "questao_ids_alvo")
        self.questao_ids_concluidas = _validar_colecao_uuids(self.questao_ids_concluidas, "questao_ids_concluidas")

        if self.escopo == EscopoExecucao.PROVA_ID:
            if self.escopo_prova_id is None:
                raise ErroValidacaoDominio("Execução com escopo 'prova_id' exige 'escopo_prova_id'.")
            if self.escopo_questao_ids:
                raise ErroValidacaoDominio("Execução com escopo 'prova_id' não aceita 'escopo_questao_ids'.")
        elif self.escopo == EscopoExecucao.QUESTAO_IDS:
            if not self.escopo_questao_ids:
                raise ErroValidacaoDominio("Execução com escopo 'questao_ids' exige 'escopo_questao_ids' não vazio.")
            if self.escopo_prova_id is not None:
                raise ErroValidacaoDominio("Execução com escopo 'questao_ids' não aceita 'escopo_prova_id'.")
        else:
            if self.escopo_prova_id is not None or self.escopo_questao_ids:
                raise ErroValidacaoDominio(
                    f"Execução com escopo '{self.escopo.value}' não aceita 'escopo_prova_id' nem 'escopo_questao_ids'."
                )

        if not isinstance(self.erros_por_questao, Mapping):
            raise ErroValidacaoDominio("'erros_por_questao' deve ser um mapeamento.")
        self.erros_por_questao = {str(k): str(v) for k, v in self.erros_por_questao.items()}

        for nome, val in (
            ("total_itens", self.total_itens),
            ("processadas", self.processadas),
            ("divergencias_abertas", self.divergencias_abertas),
            ("cache_hits", self.cache_hits),
            ("prompt_tokens", self.prompt_tokens),
            ("completion_tokens", self.completion_tokens),
        ):
            _validar_nao_negativo_int(val, nome)

    def iniciar(self, agora: datetime, total_itens: int | None = None) -> None:
        if self.status not in {StatusExecucaoClassificacao.PENDENTE, StatusExecucaoClassificacao.INTERROMPIDA}:
            raise ErroInvarianteDominio(f"Não é possível iniciar execução no estado '{self.status.value}'.")
        if total_itens is not None:
            self.total_itens = _validar_nao_negativo_int(total_itens, "total_itens")
        self.status = StatusExecucaoClassificacao.PROCESSANDO
        if self.iniciada_em is None:
            self.iniciada_em = agora
        self.concluida_em = None

    def preparar_retomada(self) -> None:
        if self.status not in {
            StatusExecucaoClassificacao.INTERROMPIDA,
            StatusExecucaoClassificacao.CONCLUIDA_COM_ERROS,
        }:
            raise ErroInvarianteDominio(
                f"Só é possível retomar execução em 'interrompida' ou 'concluida_com_erros'; "
                f"estado atual: '{self.status.value}'."
            )
        self.status = StatusExecucaoClassificacao.PENDENTE
        self.concluida_em = None
        self.erros_por_questao.clear()
        self.processadas = len(self.questao_ids_concluidas)

    def questao_ids_pendentes(self) -> list[UUID]:
        concluidas = set(self.questao_ids_concluidas)
        return [qid for qid in self.questao_ids_alvo if qid not in concluidas]

    def _recalcular_processadas(self) -> None:
        concluidas = {str(qid) for qid in self.questao_ids_concluidas}
        falhas = set(self.erros_por_questao.keys())
        self.processadas = len(concluidas | falhas)

    def registrar_sucesso_item(
        self,
        questao_id: UUID,
        *,
        cache_hit: bool = False,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        abriu_divergencia: bool = False,
    ) -> None:
        if self.status != StatusExecucaoClassificacao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível registrar resultado com execução em 'processando'; estado atual: '{self.status.value}'."
            )
        _validar_nao_negativo_int(prompt_tokens, "prompt_tokens")
        _validar_nao_negativo_int(completion_tokens, "completion_tokens")

        self.erros_por_questao.pop(str(questao_id), None)
        if questao_id not in self.questao_ids_concluidas:
            self.questao_ids_concluidas = (*self.questao_ids_concluidas, questao_id)
        if cache_hit:
            self.cache_hits += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        if abriu_divergencia:
            self.divergencias_abertas += 1
        self._recalcular_processadas()

    def registrar_pulo_item(self, questao_id: UUID) -> None:
        if self.status != StatusExecucaoClassificacao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível registrar pulo com execução em 'processando'; estado atual: '{self.status.value}'."
            )
        self.erros_por_questao.pop(str(questao_id), None)
        if questao_id not in self.questao_ids_concluidas:
            self.questao_ids_concluidas = (*self.questao_ids_concluidas, questao_id)
        self._recalcular_processadas()

    def registrar_erro_item(
        self,
        questao_id: UUID,
        mensagem: str,
        *,
        cache_hit: bool = False,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        if self.status != StatusExecucaoClassificacao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível registrar erro com execução em 'processando'; estado atual: '{self.status.value}'."
            )
        _validar_nao_negativo_int(prompt_tokens, "prompt_tokens")
        _validar_nao_negativo_int(completion_tokens, "completion_tokens")

        msg = mensagem.strip() or "Erro desconhecido ao classificar questão."
        self.erros_por_questao[str(questao_id)] = msg
        if questao_id in self.questao_ids_concluidas:
            self.questao_ids_concluidas = tuple(qid for qid in self.questao_ids_concluidas if qid != questao_id)
        if cache_hit:
            self.cache_hits += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self._recalcular_processadas()

    def reconstruir_taxonomia_snapshot(self) -> Taxonomia:
        dados = dict(self.snapshot_taxonomia)
        if dados.get("id") is None:
            dados["id"] = self.taxonomia_id
        return Taxonomia.de_snapshot(dados)

    def reconstruir_perfil_snapshot(self) -> PerfilClassificacao:
        dados = dict(self.snapshot_perfil)
        if dados.get("id") is None:
            dados["id"] = self.perfil_id
        return PerfilClassificacao.de_snapshot(dados)

    def concluir(self, agora: datetime) -> None:
        if self.status != StatusExecucaoClassificacao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível concluir execução em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = (
            StatusExecucaoClassificacao.CONCLUIDA_COM_ERROS
            if self.erros_por_questao
            else StatusExecucaoClassificacao.CONCLUIDA
        )
        self.concluida_em = agora

    def falhar(self, agora: datetime) -> None:
        if self.status != StatusExecucaoClassificacao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível falhar execução em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = StatusExecucaoClassificacao.ERRO
        self.concluida_em = agora

    def interromper(self, agora: datetime) -> None:
        if self.status != StatusExecucaoClassificacao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível interromper execução em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = StatusExecucaoClassificacao.INTERROMPIDA
        self.concluida_em = agora
