"""Prova e faixa de questões."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from domain.exceptions import ErroValidacaoDominio
from domain.prova._validacao import _validar_inteiro_positivo


@dataclass(frozen=True, slots=True)
class FaixaQuestoes:
    """Faixa inclusiva de números oficiais de questões de uma Prova."""

    inicio: int
    fim: int

    def __post_init__(self) -> None:
        _validar_inteiro_positivo(self.inicio, "inicio")
        _validar_inteiro_positivo(self.fim, "fim")
        if self.fim < self.inicio:
            raise ErroValidacaoDominio(
                f"FaixaQuestoes inválida: 'fim' ({self.fim}) deve ser >= 'inicio' ({self.inicio})."
            )

    def contem(self, numero: int) -> bool:
        return self.inicio <= numero <= self.fim

    def numeros(self) -> range:
        return range(self.inicio, self.fim + 1)

    def __len__(self) -> int:
        return self.fim - self.inicio + 1


@dataclass(slots=True)
class Prova:
    """Caderno oficial de um exame acadêmico, único por (exame, curso, ano)."""

    exame: str
    curso: str
    ano: int
    faixa_ce: FaixaQuestoes | None = None
    id: UUID = field(default_factory=uuid4)
    caminho_pdf: str | None = None
    caminho_gabarito: str | None = None
    caminho_extracao_bruta: str | None = None
    criada_em: datetime | None = None
    atualizada_em: datetime | None = None

    def __post_init__(self) -> None:
        self.exame = self.exame.strip()
        self.curso = self.curso.strip()
        if not self.exame:
            raise ErroValidacaoDominio("'exame' da Prova não pode ser vazio.")
        if not self.curso:
            raise ErroValidacaoDominio("'curso' da Prova não pode ser vazio.")
        if isinstance(self.ano, bool) or not isinstance(self.ano, int) or self.ano < 1900:
            raise ErroValidacaoDominio(f"'ano' da Prova inválido: {self.ano!r}.")
        if self.faixa_ce is None:
            from domain.faixas_enade import resolver_faixa_componente_especifico

            self.faixa_ce = resolver_faixa_componente_especifico(self.ano)

    @property
    def chave_natural(self) -> tuple[str, str, int]:
        return (self.exame.upper(), self.curso, self.ano)
