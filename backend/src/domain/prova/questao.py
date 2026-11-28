"""Questão de prova e seus objetos de valor."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from domain.enums import (
    CodigoAlertaExtracao,
    ComponenteProva,
    LetraAlternativa,
    OrigemAtivoVisual,
    SituacaoGabarito,
    TipoQuestao,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova._validacao import _validar_inteiro_nao_negativo, _validar_inteiro_positivo
from domain.prova.alerta_extracao import AlertaExtracao


def _copiar_lista_validada(valor: Iterable[Any], campo: str) -> list[Any]:
    if isinstance(valor, str | bytes | bytearray | memoryview | Mapping) or not isinstance(valor, Iterable):
        raise ErroValidacaoDominio(
            f"'{campo}' deve ser uma sequência ou coleção iterável válida (não str/bytes/Mapping)."
        )
    return list(valor)


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Caixa delimitadora normalizada (x0 < x1, y0 < y1)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        for nome, val in (("x0", self.x0), ("y0", self.y0), ("x1", self.x1), ("y1", self.y1)):
            if isinstance(val, bool) or not isinstance(val, int | float) or not math.isfinite(val):
                raise ErroValidacaoDominio(f"Coordenada '{nome}' da BoundingBox deve ser finita; recebido: {val!r}.")
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            coords = f"({self.x0}, {self.y0}, {self.x1}, {self.y1})"
            raise ErroValidacaoDominio(f"BoundingBox degenerada: esperado x0 < x1 e y0 < y1; recebido {coords}.")


@dataclass(frozen=True, slots=True)
class Gabarito:
    """Registro oficial de resposta correta ou anulação de uma Questão."""

    situacao_gabarito: SituacaoGabarito = SituacaoGabarito.PENDENTE
    alternativa_correta: LetraAlternativa | None = None

    def __post_init__(self) -> None:
        try:
            situacao = SituacaoGabarito(self.situacao_gabarito)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Situação de gabarito inválida: {self.situacao_gabarito!r}.") from err
        object.__setattr__(self, "situacao_gabarito", situacao)

        if self.alternativa_correta is not None:
            try:
                letra = LetraAlternativa(self.alternativa_correta)
            except ValueError as err:
                raise ErroValidacaoDominio(
                    f"Alternativa correta inválida no gabarito: {self.alternativa_correta!r}."
                ) from err
            object.__setattr__(self, "alternativa_correta", letra)

        if situacao == SituacaoGabarito.VALIDA and self.alternativa_correta is None:
            raise ErroValidacaoDominio("Gabarito 'valida' exige alternativa_correta definida (A..E).")
        if situacao in {SituacaoGabarito.ANULADA, SituacaoGabarito.PENDENTE} and self.alternativa_correta is not None:
            raise ErroValidacaoDominio(f"Gabarito '{situacao.value}' não pode definir alternativa_correta.")


@dataclass(frozen=True, slots=True)
class Alternativa:
    """Opção de resposta (A..E) pertencente a uma Questão objetiva."""

    letra: LetraAlternativa
    texto: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        try:
            letra = LetraAlternativa(self.letra)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Letra de alternativa inválida: {self.letra!r}.") from err
        object.__setattr__(self, "letra", letra)


@dataclass(slots=True)
class AtivoVisual:
    """Elemento gráfico extraído de uma Prova ou enviado manualmente na curadoria."""

    origem: OrigemAtivoVisual
    ordem: int = 0
    alternativa_letra: LetraAlternativa | None = None
    pagina: int | None = None
    bbox: BoundingBox | None = None
    chave_arquivo: str | None = None
    id: UUID = field(default_factory=uuid4)
    questao_id: UUID | None = None

    def __post_init__(self) -> None:
        try:
            self.origem = OrigemAtivoVisual(self.origem)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Origem de ativo visual inválida: {self.origem!r}.") from err

        _validar_inteiro_nao_negativo(self.ordem, "ordem")

        if self.alternativa_letra is not None:
            try:
                self.alternativa_letra = LetraAlternativa(self.alternativa_letra)
            except ValueError as err:
                raise ErroValidacaoDominio(
                    f"Letra de alternativa inválida no ativo visual: {self.alternativa_letra!r}."
                ) from err

        if self.pagina is not None:
            _validar_inteiro_positivo(self.pagina, "pagina")

        if (
            self.origem in {OrigemAtivoVisual.PICTURE_DOCLING, OrigemAtivoVisual.FORMULA_RECORTE}
            and self.pagina is None
        ):
            raise ErroValidacaoDominio(f"AtivoVisual com origem '{self.origem.value}' exige número de página válido.")


@dataclass(slots=True)
class Questao:
    """Item individual extraído de uma Prova, desacoplado de classificações."""

    prova_id: UUID
    numero: int
    enunciado: str
    componente: ComponenteProva = ComponenteProva.COMPONENTE_ESPECIFICO
    tipo: TipoQuestao = TipoQuestao.OBJETIVA
    paginas: tuple[int, ...] = ()
    alternativas: list[Alternativa] = field(default_factory=list)
    ativos_visuais: list[AtivoVisual] = field(default_factory=list)
    gabarito: Gabarito = field(default_factory=Gabarito)
    alertas_extracao: list[AlertaExtracao] = field(default_factory=list)
    editada_manualmente: bool = False
    id: UUID = field(default_factory=uuid4)
    versao: int = 1

    def __post_init__(self) -> None:
        _validar_inteiro_positivo(self.numero, "numero")
        _validar_inteiro_positivo(self.versao, "versao")
        try:
            self.componente = ComponenteProva(self.componente)
            self.tipo = TipoQuestao(self.tipo)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Componente ou tipo de questão inválido: {err}") from err

        self.paginas = tuple(_validar_inteiro_positivo(p, "paginas") for p in self.paginas)
        self.alternativas = _copiar_lista_validada(self.alternativas, "alternativas")
        self.ativos_visuais = _copiar_lista_validada(self.ativos_visuais, "ativos_visuais")
        self.alertas_extracao = _copiar_lista_validada(self.alertas_extracao, "alertas_extracao")
        self._validar_alternativas(self.alternativas)
        self._validar_alertas(self.alertas_extracao)

    @staticmethod
    def _validar_alternativas(alternativas: list[Alternativa]) -> None:
        vistas: set[LetraAlternativa] = set()
        for alt in alternativas:
            if alt.letra in vistas:
                raise ErroValidacaoDominio(f"Alternativa duplicada para letra '{alt.letra.value}'.")
            vistas.add(alt.letra)

    @staticmethod
    def _validar_alertas(alertas: list[AlertaExtracao]) -> None:
        vistos: set[CodigoAlertaExtracao] = set()
        for alerta in alertas:
            if alerta.codigo in vistos:
                raise ErroValidacaoDominio(f"Alerta duplicado para código '{alerta.codigo.value}'.")
            vistos.add(alerta.codigo)

    @property
    def tem_alerta_critico_aberto(self) -> bool:
        return any(a.is_critico and a.is_aberto for a in self.alertas_extracao)

    @property
    def codigos_alertas_abertos(self) -> set[CodigoAlertaExtracao]:
        return {a.codigo for a in self.alertas_extracao if a.is_aberto}

    def editar_conteudo(
        self,
        *,
        enunciado: str | None = None,
        alternativas: list[Alternativa] | None = None,
        gabarito: Gabarito | None = None,
    ) -> None:
        if enunciado is not None and not enunciado.strip():
            raise ErroValidacaoDominio("O enunciado não pode ser vazio.")
        if alternativas is not None:
            copia_alternativas = _copiar_lista_validada(alternativas, "alternativas")
            self._validar_alternativas(copia_alternativas)
            if self.tipo == TipoQuestao.OBJETIVA and not copia_alternativas:
                raise ErroValidacaoDominio("Questão objetiva exige ao menos uma alternativa.")
            self.alternativas = copia_alternativas
        if enunciado is not None:
            self.enunciado = enunciado
        if gabarito is not None:
            self.gabarito = gabarito
        self.editada_manualmente = True

    def aplicar_gabarito_oficial(self, gabarito: Gabarito) -> None:
        """Atualiza o gabarito oficial sem marcar edição manual de conteúdo."""
        self.gabarito = gabarito
