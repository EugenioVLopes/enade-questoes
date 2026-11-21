"""Entidades e objetos de valor de Taxonomia Curricular (Taxonomia, Disciplina, Tópico)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from domain.exceptions import ErroValidacaoDominio

MAX_CHARS_TOPICO = 32
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def normalizar_topico(raw: str) -> str:
    """Normaliza texto livre para slug ASCII kebab-case de até 32 caracteres sem cortar palavras.

    Se o próprio primeiro token contínuo exceder 32 caracteres, retorna string vazia para
    evitar corte no meio da palavra.
    """
    if not isinstance(raw, str):
        return ""

    ascii_text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower().strip()
    slug = _NON_ALNUM_PATTERN.sub("-", ascii_text).strip("-")
    if not slug:
        return ""

    tokens = [token for token in slug.split("-") if token]
    if not tokens or len(tokens[0]) > MAX_CHARS_TOPICO:
        return ""

    selecionados: list[str] = []
    comprimento = 0
    for token in tokens:
        adicional = len(token) if not selecionados else len(token) + 1
        if comprimento + adicional > MAX_CHARS_TOPICO:
            break
        selecionados.append(token)
        comprimento += adicional

    return "-".join(selecionados)


@dataclass(frozen=True, slots=True)
class Topico:
    """Rótulo granular livre em kebab-case ASCII (máx. 32 chars, sem corte de palavras)."""

    valor: str

    def __post_init__(self) -> None:
        normalizado = normalizar_topico(self.valor)
        if not normalizado:
            raise ErroValidacaoDominio(
                f"Tópico inválido ou maior que {MAX_CHARS_TOPICO} caracteres em token único: {self.valor!r}."
            )
        object.__setattr__(self, "valor", normalizado)

    @classmethod
    def criar(cls, raw: str) -> Topico:
        return cls(valor=raw)

    def __str__(self) -> str:
        return self.valor


@dataclass(slots=True)
class Disciplina:
    """Unidade curricular pertencente a uma Taxonomia."""

    codigo: str
    nome: str
    ementa: str = ""
    ativa: bool = True
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.codigo = self.codigo.strip()
        self.nome = self.nome.strip()
        self.ementa = self.ementa.strip()
        if not self.codigo:
            raise ErroValidacaoDominio("'codigo' da Disciplina não pode ser vazio.")
        if not self.nome:
            raise ErroValidacaoDominio("'nome' da Disciplina não pode ser vazio.")

    def arquivar(self) -> None:
        self.ativa = False

    def reativar(self) -> None:
        self.ativa = True


@dataclass(slots=True)
class Taxonomia:
    """Catálogo nomeado e editável de Disciplinas usado para classificação."""

    codigo: str
    nome: str
    curso_referencia: str = ""
    disciplinas: list[Disciplina] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        self.codigo = self.codigo.strip()
        self.nome = self.nome.strip()
        self.curso_referencia = self.curso_referencia.strip()
        if not self.codigo:
            raise ErroValidacaoDominio("'codigo' da Taxonomia não pode ser vazio.")
        if not self.nome:
            raise ErroValidacaoDominio("'nome' da Taxonomia não pode ser vazio.")

        if isinstance(self.disciplinas, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
            self.disciplinas, Iterable
        ):
            raise ErroValidacaoDominio(
                "'disciplinas' da Taxonomia deve ser uma coleção iterável de Disciplina (não str/bytes/Mapping)."
            )
        self.disciplinas = list(self.disciplinas)

        codigos: set[str] = set()
        for disciplina in self.disciplinas:
            if not isinstance(disciplina, Disciplina):
                raise ErroValidacaoDominio(
                    f"Item de 'disciplinas' da Taxonomia deve ser Disciplina; recebido: {disciplina!r}."
                )
            if disciplina.codigo in codigos:
                raise ErroValidacaoDominio(f"Disciplina duplicada na Taxonomia '{self.codigo}': '{disciplina.codigo}'.")
            codigos.add(disciplina.codigo)

    def ativas(self) -> list[Disciplina]:
        return [d for d in self.disciplinas if d.ativa]

    def mapa_ativas(self) -> dict[str, Disciplina]:
        return {d.codigo: d for d in self.disciplinas if d.ativa}

    def mapa_todas(self) -> dict[str, Disciplina]:
        return {d.codigo: d for d in self.disciplinas}

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "codigo": self.codigo,
            "nome": self.nome,
            "curso_referencia": self.curso_referencia,
            "disciplinas": [
                {
                    "id": str(d.id),
                    "codigo": d.codigo,
                    "nome": d.nome,
                    "ementa": d.ementa,
                    "ativa": d.ativa,
                }
                for d in self.ativas()
            ],
        }
