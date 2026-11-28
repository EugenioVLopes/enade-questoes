"""Classificação, curadoria humana e divergência de reclassificação."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from domain.enums import (
    OrigemClassificacao,
    ResolucaoDivergencia,
    StatusClassificacao,
    StatusDivergencia,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.taxonomia import normalizar_topico


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

        nova = criar_classificacao_humana(
            questao_id=self.questao_id,
            taxonomia_id=self.taxonomia_id,
            disciplina_principal=disciplina_principal,
            disciplinas_secundarias=disciplinas_secundarias,
            topicos=topicos,
            justificativa=justificativa,
            agora=agora,
            confianca=confianca,
            substitui_classificacao_id=self.id,
        )
        self.vigente = False
        return nova


def normalizar_topicos_curadoria(topicos: Iterable[str]) -> tuple[str, ...]:
    """Normaliza tópicos informados na curadoria humana (0..N, kebab-case ASCII, sem duplicatas)."""
    normalizados: list[str] = []
    for raw in _validar_colecao_strings(topicos, "topicos"):
        norm = normalizar_topico(raw)
        if not norm:
            raise ErroValidacaoDominio(f"Tópico inválido ou vazio após normalização: {raw!r}.")
        if norm not in normalizados:
            normalizados.append(norm)
    return tuple(normalizados)


def criar_classificacao_humana(
    *,
    questao_id: UUID,
    taxonomia_id: UUID,
    disciplina_principal: str,
    disciplinas_secundarias: Iterable[str] = (),
    topicos: Iterable[str] = (),
    justificativa: str = "",
    agora: datetime,
    confianca: float = 1.0,
    substitui_classificacao_id: UUID | None = None,
) -> Classificacao:
    """Cria uma Classificação humana aprovada e vigente (correção ou classificação manual inicial)."""
    return Classificacao(
        questao_id=questao_id,
        taxonomia_id=taxonomia_id,
        disciplina_principal=disciplina_principal,
        disciplinas_secundarias=disciplinas_secundarias,  # type: ignore[arg-type]
        topicos=normalizar_topicos_curadoria(topicos),
        justificativa=justificativa.strip(),
        confianca=confianca,
        origem=OrigemClassificacao.HUMANA,
        status=StatusClassificacao.APROVADA,
        vigente=True,
        revisao_prioritaria=False,
        execucao_id=None,
        substitui_classificacao_id=substitui_classificacao_id,
        alertas_validacao=(),
        criada_em=agora,
        revisada_em=agora,
    )


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
