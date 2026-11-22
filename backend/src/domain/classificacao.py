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
from domain.taxonomia import Taxonomia, normalizar_topico


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

    @classmethod
    def de_snapshot(cls, snapshot: Mapping[str, Any]) -> PerfilClassificacao:
        if not isinstance(snapshot, Mapping):
            raise ErroValidacaoDominio("'snapshot_perfil' deve ser um mapeamento.")

        codigo = snapshot.get("codigo")
        versao = snapshot.get("versao")
        diretrizes_gerais = snapshot.get("diretrizes_gerais")
        guia_fronteiras = snapshot.get("guia_fronteiras", "")
        template_prompt = snapshot.get("template_prompt")
        descricao = snapshot.get("descricao", "")

        for nome_campo, valor in (
            ("codigo", codigo),
            ("versao", versao),
            ("diretrizes_gerais", diretrizes_gerais),
            ("template_prompt", template_prompt),
        ):
            if not isinstance(valor, str):
                raise ErroValidacaoDominio(f"'{nome_campo}' no snapshot de PerfilClassificacao deve ser string.")

        if guia_fronteiras is None:
            guia_fronteiras = ""
        if not isinstance(guia_fronteiras, str):
            raise ErroValidacaoDominio("'guia_fronteiras' no snapshot de PerfilClassificacao deve ser string.")
        if descricao is None:
            descricao = ""
        if not isinstance(descricao, str):
            raise ErroValidacaoDominio("'descricao' no snapshot de PerfilClassificacao deve ser string.")

        raw_id = snapshot.get("id")
        if raw_id is None:
            perfil_id = uuid4()
        elif isinstance(raw_id, UUID):
            perfil_id = raw_id
        else:
            try:
                perfil_id = UUID(str(raw_id))
            except (ValueError, TypeError, AttributeError) as err:
                raise ErroValidacaoDominio(f"'id' inválido no snapshot de PerfilClassificacao: {raw_id!r}.") from err

        criado_em = snapshot.get("criado_em")
        if criado_em is not None and not isinstance(criado_em, datetime):
            criado_em = None

        return cls(
            id=perfil_id,
            codigo=codigo,
            versao=versao,
            diretrizes_gerais=diretrizes_gerais,
            guia_fronteiras=guia_fronteiras,
            template_prompt=template_prompt,
            descricao=descricao,
            criado_em=criado_em,
        )


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
