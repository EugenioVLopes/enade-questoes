"""Alerta de extração e tabelas de severidade por código."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar
from uuid import UUID, uuid4

from domain.enums import CodigoAlertaExtracao, SeveridadeAlerta, StatusAlerta
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio

SEVERIDADE_POR_CODIGO: dict[CodigoAlertaExtracao, SeveridadeAlerta] = {
    CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.PDF_VIA_OCR: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.ENUNCIADO_SUSPEITO: SeveridadeAlerta.CRITICO,
    CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA: SeveridadeAlerta.INFORMATIVO,
    CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA: SeveridadeAlerta.INFORMATIVO,
}


ALERTAS_ESTRUTURAIS: frozenset[CodigoAlertaExtracao] = frozenset(
    {
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
        CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA,
    }
)


ALERTAS_INSPECAO: frozenset[CodigoAlertaExtracao] = frozenset(
    {
        CodigoAlertaExtracao.PDF_VIA_OCR,
        CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA,
    }
)


@dataclass(slots=True)
class AlertaExtracao:
    """Sinalização determinística de anomalia de extração em uma Questão."""

    SEVERIDADE_POR_CODIGO: ClassVar[dict[CodigoAlertaExtracao, SeveridadeAlerta]] = SEVERIDADE_POR_CODIGO
    ALERTAS_ESTRUTURAIS: ClassVar[frozenset[CodigoAlertaExtracao]] = ALERTAS_ESTRUTURAIS
    ALERTAS_INSPECAO: ClassVar[frozenset[CodigoAlertaExtracao]] = ALERTAS_INSPECAO

    codigo: CodigoAlertaExtracao
    severidade: SeveridadeAlerta | None = None
    status: StatusAlerta = StatusAlerta.ABERTO
    mensagem: str = ""
    resolvido_em: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        try:
            self.codigo = CodigoAlertaExtracao(self.codigo)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Código de alerta inválido: {self.codigo!r}.") from err

        severidade_esperada = SEVERIDADE_POR_CODIGO[self.codigo]
        if self.severidade is None:
            self.severidade = severidade_esperada
        else:
            try:
                self.severidade = SeveridadeAlerta(self.severidade)
            except ValueError as err:
                raise ErroValidacaoDominio(f"Severidade de alerta inválida: {self.severidade!r}.") from err
            if self.severidade != severidade_esperada:
                raise ErroValidacaoDominio(
                    f"Severidade '{self.severidade.value}' incompatível com alerta '{self.codigo.value}' "
                    f"(esperado '{severidade_esperada.value}')."
                )

        try:
            self.status = StatusAlerta(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Status de alerta inválido: {self.status!r}.") from err

        if self.resolvido_em is not None and not isinstance(self.resolvido_em, datetime):
            raise ErroValidacaoDominio(f"'resolvido_em' deve ser um datetime válido; recebido: {self.resolvido_em!r}.")
        if self.status == StatusAlerta.ABERTO and self.resolvido_em is not None:
            raise ErroInvarianteDominio("Alerta 'aberto' não pode possuir resolvido_em.")
        if self.status == StatusAlerta.RESOLVIDO and self.resolvido_em is None:
            raise ErroInvarianteDominio("Alerta 'resolvido' exige timestamp resolvido_em.")

    @property
    def is_critico(self) -> bool:
        return self.severidade == SeveridadeAlerta.CRITICO

    @property
    def is_aberto(self) -> bool:
        return self.status == StatusAlerta.ABERTO

    @property
    def is_estrutural(self) -> bool:
        return self.codigo in ALERTAS_ESTRUTURAIS

    @property
    def is_inspecao(self) -> bool:
        return self.codigo in ALERTAS_INSPECAO

    def resolver(self, agora: datetime) -> None:
        if not isinstance(agora, datetime):
            raise ErroValidacaoDominio(f"'agora' deve ser um datetime válido ao resolver alerta; recebido: {agora!r}.")
        self.status = StatusAlerta.RESOLVIDO
        self.resolvido_em = agora

    def reabrir(self, mensagem: str | None = None) -> None:
        self.status = StatusAlerta.ABERTO
        self.resolvido_em = None
        if mensagem is not None:
            self.mensagem = mensagem
