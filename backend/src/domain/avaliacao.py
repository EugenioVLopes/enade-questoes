"""Entidades e objetos de valor de Avaliação Offline (Conjunto-Ouro e Avaliação)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from domain.classificacao import Classificacao
from domain.enums import SituacaoGabarito, StatusClassificacao
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova import AlertaExtracao
from domain.taxonomia import Taxonomia


@dataclass(frozen=True, slots=True)
class ChaveQuestaoOuro:
    """Chave natural estável de uma Questão no Conjunto-Ouro (sem UUID)."""

    exame: str
    curso: str
    ano: int
    numero: int

    def __post_init__(self) -> None:
        exame = self.exame.strip().upper()
        curso = self.curso.strip()
        if not exame:
            raise ErroValidacaoDominio("'exame' da ChaveQuestaoOuro não pode ser vazio.")
        if not curso:
            raise ErroValidacaoDominio("'curso' da ChaveQuestaoOuro não pode ser vazio.")
        if isinstance(self.ano, bool) or not isinstance(self.ano, int) or self.ano < 1900:
            raise ErroValidacaoDominio(f"'ano' inválido na ChaveQuestaoOuro: {self.ano!r}.")
        if isinstance(self.numero, bool) or not isinstance(self.numero, int) or self.numero < 1:
            raise ErroValidacaoDominio(f"'numero' inválido na ChaveQuestaoOuro: {self.numero!r}.")
        object.__setattr__(self, "exame", exame)
        object.__setattr__(self, "curso", curso)

    def as_tuple(self) -> tuple[str, str, int, int]:
        return (self.exame, self.curso, self.ano, self.numero)


@dataclass(frozen=True, slots=True)
class ItemConjuntoOuro:
    """Item verificado por humano pertencente a um Conjunto-Ouro."""

    chave: ChaveQuestaoOuro
    disciplina_principal: str
    disciplinas_secundarias: tuple[str, ...] = ()
    situacao_gabarito: SituacaoGabarito = SituacaoGabarito.VALIDA
    notas: str = ""

    def __post_init__(self) -> None:
        principal = self.disciplina_principal.strip()
        if not principal:
            raise ErroValidacaoDominio("'disciplina_principal' do ItemConjuntoOuro não pode ser vazia.")
        object.__setattr__(self, "disciplina_principal", principal)

        if isinstance(self.disciplinas_secundarias, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
            self.disciplinas_secundarias, Iterable
        ):
            raise ErroValidacaoDominio(
                "'disciplinas_secundarias' do ItemConjuntoOuro deve ser uma coleção iterável de strings "
                "(não str/bytes/Mapping)."
            )

        sec_limpas: list[str] = []
        vistas: set[str] = set()
        for raw in self.disciplinas_secundarias:
            if not isinstance(raw, str):
                raise ErroValidacaoDominio(
                    f"Disciplina secundária do ItemConjuntoOuro deve ser string; recebido: {raw!r}."
                )
            sec = raw.strip()
            if not sec:
                raise ErroValidacaoDominio("Disciplina secundária do ItemConjuntoOuro não pode ser vazia.")
            if sec == principal:
                raise ErroValidacaoDominio("Disciplina secundária do ItemConjuntoOuro não pode igualar principal.")
            if sec in vistas:
                raise ErroValidacaoDominio(f"Disciplina secundária duplicada no ItemConjuntoOuro: '{sec}'.")
            vistas.add(sec)
            sec_limpas.append(sec)
        if len(sec_limpas) > 2:
            raise ErroValidacaoDominio("ItemConjuntoOuro aceita no máximo 2 disciplinas secundárias.")
        object.__setattr__(self, "disciplinas_secundarias", tuple(sec_limpas))

        try:
            situacao = SituacaoGabarito(self.situacao_gabarito)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Situação de gabarito inválida: {self.situacao_gabarito!r}.") from err
        object.__setattr__(self, "situacao_gabarito", situacao)


@dataclass(frozen=True, slots=True)
class ConjuntoOuro:
    """Snapshot versionado e ordenado determinístico de vereditos aprovados."""

    versao_schema: str
    taxonomia_codigo: str
    exportado_em: datetime
    itens: tuple[ItemConjuntoOuro, ...]

    def __post_init__(self) -> None:
        versao = self.versao_schema.strip()
        taxonomia = self.taxonomia_codigo.strip()
        if not versao:
            raise ErroValidacaoDominio("'versao_schema' do ConjuntoOuro não pode ser vazia.")
        if not taxonomia:
            raise ErroValidacaoDominio("'taxonomia_codigo' do ConjuntoOuro não pode ser vazio.")
        object.__setattr__(self, "versao_schema", versao)
        object.__setattr__(self, "taxonomia_codigo", taxonomia)

        if isinstance(self.itens, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
            self.itens, Iterable
        ):
            raise ErroValidacaoDominio(
                "'itens' do ConjuntoOuro deve ser uma coleção iterável de ItemConjuntoOuro (não str/bytes/Mapping)."
            )
        itens_materializados = tuple(self.itens)

        vistas: set[ChaveQuestaoOuro] = set()
        for item in itens_materializados:
            if not isinstance(item, ItemConjuntoOuro):
                raise ErroValidacaoDominio(
                    f"Item de 'itens' do ConjuntoOuro deve ser ItemConjuntoOuro; recebido: {item!r}."
                )
            if item.chave in vistas:
                raise ErroValidacaoDominio(f"Chave duplicada no ConjuntoOuro: {item.chave.as_tuple()}.")
            vistas.add(item.chave)

        ordenados = tuple(sorted(itens_materializados, key=lambda item: item.chave.as_tuple()))
        object.__setattr__(self, "itens", ordenados)

    @property
    def total_itens(self) -> int:
        return len(self.itens)

    def digest(self) -> str:
        payload = {
            "versao_schema": self.versao_schema,
            "taxonomia_codigo": self.taxonomia_codigo,
            "itens": [
                {
                    "chave": list(item.chave.as_tuple()),
                    "disciplina_principal": item.disciplina_principal,
                    "disciplinas_secundarias": sorted(item.disciplinas_secundarias),
                    "situacao_gabarito": item.situacao_gabarito.value,
                }
                for item in self.itens
            ],
        }
        serializado = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(serializado.encode("utf-8")).hexdigest()

    @staticmethod
    def item_elegivel(
        classificacao: Classificacao | None,
        alertas_extracao: Sequence[AlertaExtracao],
    ) -> bool:
        """Verifica elegibilidade: classificação vigente aprovada e zero alerta crítico aberto."""
        if classificacao is None or not classificacao.vigente:
            return False
        if classificacao.status != StatusClassificacao.APROVADA:
            return False
        return not any(alerta.is_critico and alerta.is_aberto for alerta in alertas_extracao)

    def validar_preflight(
        self,
        taxonomia: Taxonomia,
        alertas_por_chave: Mapping[ChaveQuestaoOuro, Sequence[AlertaExtracao]],
    ) -> list[str]:
        """Valida preflight antes de chamar o LLM: existência, alertas críticos e catálogo ativo."""
        erros: list[str] = []
        if taxonomia.codigo != self.taxonomia_codigo:
            erros.append(f"Taxonomia incompatível: esperado '{self.taxonomia_codigo}', recebido '{taxonomia.codigo}'.")
            return erros

        ativas = taxonomia.mapa_ativas()
        for item in self.itens:
            if item.chave not in alertas_por_chave:
                erros.append(f"Questão ausente na base local: {item.chave.as_tuple()}.")
            else:
                alertas = alertas_por_chave[item.chave]
                criticos = [a.codigo.value for a in alertas if a.is_critico and a.is_aberto]
                if criticos:
                    erros.append(f"Questão {item.chave.as_tuple()} possui alertas críticos abertos: {criticos}.")

            if item.disciplina_principal not in ativas:
                erros.append(
                    f"Questão {item.chave.as_tuple()} referencia principal inativa/inexistente: "
                    f"'{item.disciplina_principal}'."
                )
            for sec in item.disciplinas_secundarias:
                if sec not in ativas:
                    erros.append(f"Questão {item.chave.as_tuple()} referencia secundária inativa/inexistente: '{sec}'.")

        return erros

    def garantir_preflight(
        self,
        taxonomia: Taxonomia,
        alertas_por_chave: Mapping[ChaveQuestaoOuro, Sequence[AlertaExtracao]],
    ) -> None:
        erros = self.validar_preflight(taxonomia, alertas_por_chave)
        if erros:
            raise ErroInvarianteDominio("Preflight do Conjunto-Ouro falhou: " + " | ".join(erros))


@dataclass(frozen=True, slots=True)
class PredicaoClassificacao:
    """Saída normalizada de uma questão avaliada contra o Conjunto-Ouro."""

    chave: ChaveQuestaoOuro
    conclusao_valida: bool
    disciplina_principal: str | None = None
    disciplinas_secundarias: tuple[str, ...] = ()
    confianca: float = 0.0
    revisao_prioritaria: bool = False
    justificativa: str = ""
    tentativas: int = 1
    houve_saneamento: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    from_cache: bool = False
    latencia_ms: float = 0.0
    passes: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.tentativas, bool) or not isinstance(self.tentativas, int) or self.tentativas < 1:
            raise ErroValidacaoDominio(f"'tentativas' deve ser >= 1; recebido: {self.tentativas!r}.")
        if (
            isinstance(self.confianca, bool)
            or not isinstance(self.confianca, int | float)
            or not math.isfinite(self.confianca)
            or not (0.0 <= self.confianca <= 1.0)
        ):
            raise ErroValidacaoDominio(f"'confianca' deve estar em [0.0, 1.0]; recebido: {self.confianca!r}.")
        for nome, val in (("prompt_tokens", self.prompt_tokens), ("completion_tokens", self.completion_tokens)):
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise ErroValidacaoDominio(f"Contador '{nome}' deve ser inteiro >= 0; recebido: {val!r}.")
        if (
            isinstance(self.latencia_ms, bool)
            or not isinstance(self.latencia_ms, int | float)
            or not math.isfinite(self.latencia_ms)
            or self.latencia_ms < 0.0
        ):
            raise ErroValidacaoDominio(f"'latencia_ms' deve ser número finito >= 0.0; recebido: {self.latencia_ms!r}.")

        principal_limpa = self.disciplina_principal.strip() if self.disciplina_principal is not None else None
        if self.conclusao_valida and not principal_limpa:
            raise ErroValidacaoDominio("Predição com conclusao_valida=True exige disciplina_principal.")
        if principal_limpa is not None:
            object.__setattr__(self, "disciplina_principal", principal_limpa)

        if isinstance(self.disciplinas_secundarias, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
            self.disciplinas_secundarias, Iterable
        ):
            raise ErroValidacaoDominio(
                "'disciplinas_secundarias' da PredicaoClassificacao deve ser uma coleção iterável de strings "
                "(não str/bytes/Mapping)."
            )
        sec_limpas_list: list[str] = []
        for raw in self.disciplinas_secundarias:
            if not isinstance(raw, str):
                raise ErroValidacaoDominio(
                    f"Disciplina secundária da PredicaoClassificacao deve ser string; recebido: {raw!r}."
                )
            limpa = raw.strip()
            if limpa:
                sec_limpas_list.append(limpa)
        object.__setattr__(self, "disciplinas_secundarias", tuple(sec_limpas_list))


@dataclass(frozen=True, slots=True)
class ResultadoItemAvaliacao:
    """Resultado individual por questão na Avaliação de Classificação."""

    chave: ChaveQuestaoOuro
    esperada_principal: str
    esperadas_secundarias: tuple[str, ...]
    predita_principal: str | None
    preditas_secundarias: tuple[str, ...]
    conclusao_valida: bool
    principal_correta: bool
    jaccard_secundarias: float
    f1_secundarias: float
    exact_match: bool
    confianca: float
    revisao_prioritaria: bool
    justificativa: str = ""


@dataclass(frozen=True, slots=True)
class ParConfusao:
    """Par ranqueado fora da diagonal principal (esperada -> predita)."""

    esperada: str
    predita: str
    contagem: int


@dataclass(frozen=True, slots=True)
class DivergenciaAvaliacao:
    """Item divergente entre a predição e o veredito do Conjunto-Ouro."""

    chave: ChaveQuestaoOuro
    esperada_principal: str
    esperadas_secundarias: tuple[str, ...]
    predita_principal: str | None
    preditas_secundarias: tuple[str, ...]
    confianca: float
    revisao_prioritaria: bool
    trecho_justificativa: str


@dataclass(frozen=True, slots=True)
class MetricasCamada1:
    """Camada 1 — Acurácia curricular."""

    total_itens: int
    acuracia_principal: float
    macro_f1_principal: float
    jaccard_secundarias: float
    f1_secundarias: float
    exact_match: float


@dataclass(frozen=True, slots=True)
class MetricasCamada2:
    """Camada 2 — Diagnóstico de fronteiras."""

    matriz_confusao: Mapping[str, Mapping[str, int]]
    pares_confusao_ranqueados: tuple[ParConfusao, ...]
    divergencias: tuple[DivergenciaAvaliacao, ...]

    def __post_init__(self) -> None:
        congelada = MappingProxyType({k: MappingProxyType(dict(v)) for k, v in self.matriz_confusao.items()})
        object.__setattr__(self, "matriz_confusao", congelada)


@dataclass(frozen=True, slots=True)
class MetricasCamada3:
    """Camada 3 — Saúde operacional e calibração."""

    conclusao_valida: float
    validade_primeira_tentativa: float
    taxa_revisao_prioritaria: float
    taxa_erro_alta_confianca: float
    total_alta_confianca: int
    erros_alta_confianca: int
    prompt_tokens: int
    completion_tokens: int
    cache_hits: int
    cache_hit_rate: float
    latencia_media_ms: float
    latencia_p95_ms: float
    estabilidade_multipass: float | None = None


@dataclass(frozen=True, slots=True)
class AvaliacaoClassificacao:
    """Medição offline isolada (somente leitura) contra um Conjunto-Ouro."""

    taxonomia_codigo: str
    conjunto_ouro_digest: str
    perfil_codigo: str
    perfil_versao: str
    modelo_identidade: str
    executado_em: datetime
    camada1: MetricasCamada1
    camada2: MetricasCamada2
    camada3: MetricasCamada3
    itens: tuple[ResultadoItemAvaliacao, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ItemDiffGate:
    """Mudança questão-a-questão entre baseline e candidato."""

    chave: ChaveQuestaoOuro
    baseline_principal: str | None
    baseline_secundarias: tuple[str, ...]
    candidato_principal: str | None
    candidato_secundarias: tuple[str, ...]
    baseline_exact_match: bool
    candidato_exact_match: bool
    baseline_principal_correta: bool
    candidato_principal_correta: bool


@dataclass(frozen=True, slots=True)
class ResultadoGate:
    """Resultado do gate determinístico de regressão entre baseline e candidato."""

    aprovado: bool
    modo_migracao: bool
    motivos_reprovacao: tuple[str, ...]
    delta_acuracia: float
    delta_macro_f1: float
    delta_jaccard: float
    delta_exact_match: float
    ganhos: tuple[ItemDiffGate, ...]
    regressoes: tuple[ItemDiffGate, ...] = ()
