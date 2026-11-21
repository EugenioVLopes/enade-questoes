"""Entidades de Classificação, Perfis, Execuções e Divergências de Reclassificação."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from domain.enums import (
    EscopoExecucao,
    OrigemClassificacao,
    ResolucaoDivergencia,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.taxonomia import normalizar_topico


def _congelar_valor(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return MappingProxyType({k: _congelar_valor(v) for k, v in valor.items()})
    if isinstance(valor, list | tuple):
        return tuple(_congelar_valor(v) for v in valor)
    if isinstance(valor, set | frozenset):
        return frozenset(_congelar_valor(v) for v in valor)
    return valor


def _validar_confianca(confianca: float) -> float:
    if isinstance(confianca, bool) or not isinstance(confianca, int | float) or not math.isfinite(confianca):
        raise ErroValidacaoDominio(f"'confianca' deve ser número finito; recebido: {confianca!r}.")
    valor = float(confianca)
    if valor < 0.0 or valor > 1.0:
        raise ErroValidacaoDominio(f"'confianca' deve estar no intervalo [0.0, 1.0]; recebido: {valor}.")
    return valor


def _validar_secundarias(principal: str, secundarias: Iterable[str]) -> tuple[str, ...]:
    if isinstance(secundarias, str | bytes | bytearray | memoryview | Mapping) or not isinstance(secundarias, Iterable):
        raise ErroValidacaoDominio(
            "'disciplinas_secundarias' deve ser uma coleção iterável de strings (não str/bytes/Mapping)."
        )
    limpas: list[str] = []
    vistas: set[str] = set()
    for sec in secundarias:
        if not isinstance(sec, str):
            raise ErroValidacaoDominio(f"Disciplina secundária deve ser string; recebido: {sec!r}.")
        slug = sec.strip()
        if not slug:
            raise ErroValidacaoDominio("Disciplina secundária não pode ser vazia.")
        if slug == principal:
            raise ErroValidacaoDominio(f"Disciplina secundária '{slug}' não pode ser igual à principal.")
        if slug in vistas:
            raise ErroValidacaoDominio(f"Disciplina secundária duplicada: '{slug}'.")
        vistas.add(slug)
        limpas.append(slug)
    if len(limpas) > 2:
        raise ErroValidacaoDominio(f"Classificação aceita no máximo 2 disciplinas secundárias; recebido {len(limpas)}.")
    return tuple(limpas)


def _validar_colecao_strings(valor: Iterable[str], campo: str) -> tuple[str, ...]:
    if isinstance(valor, str | bytes | bytearray | memoryview | Mapping) or not isinstance(valor, Iterable):
        raise ErroValidacaoDominio(f"'{campo}' deve ser uma coleção iterável de strings (não str/bytes/Mapping).")
    itens: list[str] = []
    for item in valor:
        if not isinstance(item, str):
            raise ErroValidacaoDominio(f"Item de '{campo}' deve ser string; recebido: {item!r}.")
        itens.append(item)
    return tuple(itens)


@dataclass(frozen=True, slots=True)
class PerfilClassificacao:
    """Conjunto versionado e imutável de diretrizes, guia de fronteiras e prompt."""

    codigo: str
    versao: str
    diretrizes_gerais: str
    guia_fronteiras: str
    template_prompt: str
    descricao: str = ""
    criado_em: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        codigo = self.codigo.strip()
        versao = self.versao.strip()
        diretrizes = self.diretrizes_gerais.strip()
        template = self.template_prompt.strip()
        if not codigo:
            raise ErroValidacaoDominio("'codigo' do PerfilClassificacao não pode ser vazio.")
        if not versao:
            raise ErroValidacaoDominio("'versao' do PerfilClassificacao não pode ser vazia.")
        if not diretrizes:
            raise ErroValidacaoDominio("'diretrizes_gerais' do PerfilClassificacao não podem ser vazias.")
        if not template:
            raise ErroValidacaoDominio("'template_prompt' do PerfilClassificacao não pode ser vazio.")
        object.__setattr__(self, "codigo", codigo)
        object.__setattr__(self, "versao", versao)
        object.__setattr__(self, "diretrizes_gerais", diretrizes)
        object.__setattr__(self, "guia_fronteiras", self.guia_fronteiras.strip())
        object.__setattr__(self, "template_prompt", template)
        object.__setattr__(self, "descricao", self.descricao.strip())

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "codigo": self.codigo,
            "versao": self.versao,
            "diretrizes_gerais": self.diretrizes_gerais,
            "guia_fronteiras": self.guia_fronteiras,
            "template_prompt": self.template_prompt,
            "descricao": self.descricao,
        }


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
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        try:
            self.escopo = EscopoExecucao(self.escopo)
            self.status = StatusExecucaoClassificacao(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Escopo ou status de execução inválido: {err}") from err

        if not isinstance(self.snapshot_taxonomia, Mapping) or not self.snapshot_taxonomia:
            raise ErroValidacaoDominio("ExecucaoClassificacao exige 'snapshot_taxonomia' não vazio.")
        if not isinstance(self.snapshot_perfil, Mapping) or not self.snapshot_perfil:
            raise ErroValidacaoDominio("ExecucaoClassificacao exige 'snapshot_perfil' não vazio.")

        self.snapshot_taxonomia = _congelar_valor(self.snapshot_taxonomia)
        self.snapshot_perfil = _congelar_valor(self.snapshot_perfil)

        for nome, val in (
            ("total_itens", self.total_itens),
            ("processadas", self.processadas),
            ("divergencias_abertas", self.divergencias_abertas),
            ("cache_hits", self.cache_hits),
            ("prompt_tokens", self.prompt_tokens),
            ("completion_tokens", self.completion_tokens),
        ):
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise ErroValidacaoDominio(f"Contador '{nome}' deve ser inteiro >= 0; recebido: {val!r}.")

    def iniciar(self, agora: datetime, total_itens: int | None = None) -> None:
        if self.status not in {StatusExecucaoClassificacao.PENDENTE, StatusExecucaoClassificacao.INTERROMPIDA}:
            raise ErroInvarianteDominio(f"Não é possível iniciar execução no estado '{self.status.value}'.")
        if total_itens is not None:
            if isinstance(total_itens, bool) or not isinstance(total_itens, int) or total_itens < 0:
                raise ErroValidacaoDominio(f"'total_itens' inválido: {total_itens!r}.")
            self.total_itens = total_itens
        self.status = StatusExecucaoClassificacao.PROCESSANDO
        self.iniciada_em = agora
        self.concluida_em = None

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


@dataclass(slots=True)
class Classificacao:
    """Veredito curricular associado a um par (Questão, Taxonomia)."""

    questao_id: UUID
    taxonomia_id: UUID
    disciplina_principal: str
    disciplinas_secundarias: tuple[str, ...] = ()
    topicos: tuple[str, ...] = ()
    justificativa: str = ""
    confianca: float = 1.0
    origem: OrigemClassificacao = OrigemClassificacao.AUTOMATICA
    status: StatusClassificacao = StatusClassificacao.PENDENTE_REVISAO
    vigente: bool = True
    revisao_prioritaria: bool = False
    execucao_id: UUID | None = None
    substitui_classificacao_id: UUID | None = None
    alertas_validacao: tuple[str, ...] = ()
    criada_em: datetime | None = None
    revisada_em: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.disciplina_principal = self.disciplina_principal.strip()
        if not self.disciplina_principal:
            raise ErroValidacaoDominio("'disciplina_principal' não pode ser vazia.")

        self.disciplinas_secundarias = _validar_secundarias(
            self.disciplina_principal,
            self.disciplinas_secundarias,
        )
        self.topicos = _validar_colecao_strings(self.topicos, "topicos")
        self.confianca = _validar_confianca(self.confianca)

        try:
            self.origem = OrigemClassificacao(self.origem)
            self.status = StatusClassificacao(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Origem ou status de classificação inválido: {err}") from err

        self.alertas_validacao = _validar_colecao_strings(self.alertas_validacao, "alertas_validacao")

    def aprovar(self, agora: datetime) -> None:
        """Aprova in-place a classificação vigente (preservando origem automática)."""
        if not self.vigente:
            raise ErroInvarianteDominio("Não é possível aprovar uma classificação não vigente.")
        self.status = StatusClassificacao.APROVADA
        self.revisada_em = agora

    def substituir_por_correcao(
        self,
        *,
        disciplina_principal: str,
        disciplinas_secundarias: Iterable[str] = (),
        topicos: Iterable[str] = (),
        justificativa: str,
        agora: datetime,
        confianca: float = 1.0,
    ) -> Classificacao:
        """Cria correção humana imutável marcando a classificação anterior como não vigente.

        Diferente das travas automáticas pós-LLM (1..4 tópicos), a curadoria humana aceita
        0..N tópicos válidos normalizados em kebab-case ASCII.
        """
        if not self.vigente:
            raise ErroInvarianteDominio("Só é possível substituir uma classificação vigente.")

        topicos_validados = _validar_colecao_strings(topicos, "topicos")
        topicos_normalizados: list[str] = []
        vistos: set[str] = set()
        for raw in topicos_validados:
            norm = normalizar_topico(raw)
            if norm and norm not in vistos:
                vistos.add(norm)
                topicos_normalizados.append(norm)

        nova = Classificacao(
            questao_id=self.questao_id,
            taxonomia_id=self.taxonomia_id,
            disciplina_principal=disciplina_principal,
            disciplinas_secundarias=disciplinas_secundarias,  # type: ignore[arg-type]
            topicos=tuple(topicos_normalizados),
            justificativa=justificativa.strip(),
            confianca=confianca,
            origem=OrigemClassificacao.HUMANA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
            revisao_prioritaria=False,
            execucao_id=None,
            substitui_classificacao_id=self.id,
            alertas_validacao=(),
            criada_em=agora,
            revisada_em=agora,
        )
        self.vigente = False
        return nova


@dataclass(slots=True)
class DivergenciaReclassificacao:
    """Conflito entre classificação candidata de reexecução e classificação já aprovada."""

    questao_id: UUID
    taxonomia_id: UUID
    execucao_id: UUID
    classificacao_vigente_id: UUID
    disciplina_principal_candidata: str
    disciplinas_secundarias_candidatas: tuple[str, ...] = ()
    topicos_candidatos: tuple[str, ...] = ()
    justificativa_candidata: str = ""
    confianca_candidata: float = 0.0
    classificacao_candidata_id: UUID | None = None
    status: StatusDivergencia = StatusDivergencia.ABERTA
    resolucao: ResolucaoDivergencia | None = None
    criada_em: datetime | None = None
    resolvida_em: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.disciplina_principal_candidata = self.disciplina_principal_candidata.strip()
        if not self.disciplina_principal_candidata:
            raise ErroValidacaoDominio("'disciplina_principal_candidata' não pode ser vazia.")

        self.disciplinas_secundarias_candidatas = _validar_secundarias(
            self.disciplina_principal_candidata,
            self.disciplinas_secundarias_candidatas,
        )
        self.topicos_candidatos = _validar_colecao_strings(self.topicos_candidatos, "topicos_candidatos")
        self.confianca_candidata = _validar_confianca(self.confianca_candidata)

        try:
            self.status = StatusDivergencia(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Status de divergência inválido: {self.status!r}.") from err

        if self.resolucao is not None:
            try:
                self.resolucao = ResolucaoDivergencia(self.resolucao)
            except ValueError as err:
                raise ErroValidacaoDominio(f"Resolução de divergência inválida: {self.resolucao!r}.") from err

        if self.status == StatusDivergencia.ABERTA and (self.resolucao is not None or self.resolvida_em is not None):
            raise ErroInvarianteDominio("Divergência 'aberta' não pode ter resolução nem resolvida_em.")
        if self.status == StatusDivergencia.RESOLVIDA and (self.resolucao is None or self.resolvida_em is None):
            raise ErroInvarianteDominio("Divergência 'resolvida' exige resolução e resolvida_em.")

    def resolver(self, resolucao: ResolucaoDivergencia, agora: datetime) -> None:
        if self.status == StatusDivergencia.RESOLVIDA:
            raise ErroInvarianteDominio("Divergência já foi resolvida.")
        if not isinstance(agora, datetime):
            raise ErroValidacaoDominio(
                f"'agora' deve ser um datetime válido ao resolver divergência; recebido: {agora!r}."
            )
        try:
            resolucao_normalizada = ResolucaoDivergencia(resolucao)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Resolução de divergência inválida: {resolucao!r}.") from err
        self.resolucao = resolucao_normalizada
        self.status = StatusDivergencia.RESOLVIDA
        self.resolvida_em = agora
